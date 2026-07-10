"""
Tests for the governed agent-action spine (app/core/agent_actions.py): propose -> confirm ->
execute, with expiry and idempotency. No DB/queue - the Prisma client, dispatch and audit
are mocked.
"""
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _tool(status="active", id_="tool1", type_="spend_control"):
    m = MagicMock()
    m.id = id_
    m.type = type_
    m.status = status
    return m


def _action(status="proposed", expires_in=900, kind="run_automation", params=None):
    m = MagicMock()
    m.id = "act1"
    m.tenant_id = "t1"
    m.kind = kind
    m.capability = "write"
    m.params = params if params is not None else {"tool_id": "tool1", "tool_type": "spend_control"}
    m.status = status
    m.execution_id = None
    m.expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
    return m


def _db(tool=None, action=None, existing_exec=None):
    db = MagicMock()
    db.tool.find_first = AsyncMock(return_value=tool)
    db.agentaction.create = AsyncMock(return_value=action or _action())
    db.agentaction.find_first = AsyncMock(return_value=action)
    db.agentaction.update = AsyncMock()
    db.execution.find_first = AsyncMock(return_value=existing_exec)
    db.execution.create = AsyncMock(return_value=MagicMock(id="exec1"))
    return db


# ---- propose ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_propose_run_automation_persists_and_previews():
    db = _db(tool=_tool(), action=_action())
    from app.core.agent_actions import propose_action
    res = await propose_action(db, "t1", kind="run_automation",
                               params={"tool_type": "spend_control"}, proposed_by="u1")
    assert res["requires_confirmation"] is True
    assert res["action_id"] == "act1"
    assert "spend_control" in res["preview"]
    # persisted as proposed, tenant-scoped, with the resolved tool id
    data = db.agentaction.create.await_args.kwargs["data"]
    assert data["status"] == "proposed" and data["tenant_id"] == "t1"
    assert data["params"]["tool_id"] == "tool1"


@pytest.mark.asyncio
async def test_propose_unknown_kind_raises():
    db = _db()
    from app.core.agent_actions import propose_action, AgentActionError
    with pytest.raises(AgentActionError, match="Unknown action kind"):
        await propose_action(db, "t1", kind="nuke_everything", params={}, proposed_by="u1")


@pytest.mark.asyncio
async def test_propose_undeployed_tool_raises():
    db = _db(tool=None)
    from app.core.agent_actions import propose_action, AgentActionError
    with pytest.raises(AgentActionError, match="deployed"):
        await propose_action(db, "t1", kind="run_automation",
                             params={"tool_type": "spend_control"}, proposed_by="u1")


@pytest.mark.asyncio
async def test_propose_paused_tool_raises():
    db = _db(tool=_tool(status="inactive"))
    from app.core.agent_actions import propose_action, AgentActionError
    with pytest.raises(AgentActionError, match="paused"):
        await propose_action(db, "t1", kind="run_automation",
                             params={"tool_type": "spend_control"}, proposed_by="u1")


# ---- execute ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_dispatches_through_governed_path():
    db = _db(tool=_tool(), action=_action())
    with (
        patch("app.core.dispatch.enqueue_for_tool_type", AsyncMock()) as enq,
        patch("app.queue.pool.get_queue_pool", AsyncMock(return_value=MagicMock())),
        patch("app.core.agent_actions.write_audit_log", AsyncMock()) as audit,
    ):
        from app.core.agent_actions import execute_action
        res = await execute_action(db, "t1", "act1", confirmed_by="u1")
    assert res["executed"] is True and res["execution_id"] == "exec1"
    enq.assert_awaited_once()
    # marked executed + audited
    assert db.agentaction.update.await_args.kwargs["data"]["status"] == "executed"
    audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_expired_refuses_and_marks_expired():
    db = _db(tool=_tool(), action=_action(expires_in=-10))  # already expired
    with patch("app.core.agent_actions.write_audit_log", AsyncMock()):
        from app.core.agent_actions import execute_action, AgentActionError
        with pytest.raises(AgentActionError, match="expired"):
            await execute_action(db, "t1", "act1", confirmed_by="u1")
    assert db.agentaction.update.await_args.kwargs["data"]["status"] == "expired"
    db.execution.create.assert_not_awaited()  # nothing ran


@pytest.mark.asyncio
async def test_execute_is_idempotent_when_already_executed():
    action = _action(status="executed")
    action.execution_id = "exec1"
    db = _db(action=action)
    from app.core.agent_actions import execute_action
    res = await execute_action(db, "t1", "act1", confirmed_by="u1")
    assert res["idempotent"] is True and res["execution_id"] == "exec1"
    db.execution.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_cancelled_action_raises():
    db = _db(action=_action(status="cancelled"))
    from app.core.agent_actions import execute_action, AgentActionError
    with pytest.raises(AgentActionError, match="cannot execute"):
        await execute_action(db, "t1", "act1", confirmed_by="u1")


@pytest.mark.asyncio
async def test_execute_reuses_existing_execution():
    # a job already exists for this action's input_ref -> don't create a second
    db = _db(tool=_tool(), action=_action(), existing_exec=MagicMock(id="prior"))
    with (
        patch("app.core.dispatch.enqueue_for_tool_type", AsyncMock()) as enq,
        patch("app.queue.pool.get_queue_pool", AsyncMock(return_value=MagicMock())),
        patch("app.core.agent_actions.write_audit_log", AsyncMock()),
    ):
        from app.core.agent_actions import execute_action
        res = await execute_action(db, "t1", "act1", confirmed_by="u1")
    assert res["execution_id"] == "prior"
    db.execution.create.assert_not_awaited()
    enq.assert_not_awaited()


# ---- cancel ----------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancel_marks_cancelled():
    db = _db(action=_action())
    from app.core.agent_actions import cancel_action
    res = await cancel_action(db, "t1", "act1")
    assert res["cancelled"] is True
    assert db.agentaction.update.await_args.kwargs["data"]["status"] == "cancelled"


# ---- clen tool wrapper -----------------------------------------------------

@pytest.mark.asyncio
async def test_clen_run_automation_returns_proposal():
    db = _db(tool=_tool(), action=_action())
    from app.clen.tools import execute_tool
    res = await execute_tool("run_automation", {"tool_type": "spend_control"}, "t1", "u1", db)
    assert "proposed_action" in res
    assert res["proposed_action"]["kind"] == "run_automation"


@pytest.mark.asyncio
async def test_clen_run_automation_surfaces_error():
    db = _db(tool=None)  # not deployed
    from app.clen.tools import execute_tool
    res = await execute_tool("run_automation", {"tool_type": "spend_control"}, "t1", "u1", db)
    assert "error" in res


# ---- agent read capabilities ------------------------------------------------

@pytest.mark.asyncio
async def test_financial_summary_aggregates_and_flags_overdue():
    inv_od = MagicMock(outstanding_cents=1000, due_date=datetime.now(UTC) - timedelta(days=5), currency="GBP")
    inv_ok = MagicMock(outstanding_cents=500, due_date=datetime.now(UTC) + timedelta(days=5), currency="GBP")
    bill_od = MagicMock(outstanding_cents=800, due_date=datetime.now(UTC) - timedelta(days=2), currency="GBP")
    db = MagicMock()
    db.accountinginvoice.find_many = AsyncMock(return_value=[inv_od, inv_ok])
    db.accountingbill.find_many = AsyncMock(return_value=[bill_od])
    from app.clen.tools import execute_tool
    res = await execute_tool("get_financial_summary", {}, "t1", "u1", db)
    assert res["receivables"]["outstanding_cents"] == 1500
    assert res["receivables"]["overdue_count"] == 1 and res["receivables"]["overdue_cents"] == 1000
    assert res["payables"]["outstanding_cents"] == 800
    assert res["net_position_cents"] == 700  # 1500 receivable - 800 payable


@pytest.mark.asyncio
async def test_list_overdue_invoices_shapes_items():
    inv = MagicMock(id="i1", number="INV-1", contact_name="Acme",
                    outstanding_cents=1200, currency="GBP",
                    due_date=datetime.now(UTC) - timedelta(days=3))
    db = MagicMock()
    db.accountinginvoice.find_many = AsyncMock(return_value=[inv])
    from app.clen.tools import execute_tool
    res = await execute_tool("list_overdue_invoices", {"limit": 5}, "t1", "u1", db)
    assert res["count"] == 1
    item = res["overdue_invoices"][0]
    assert item["number"] == "INV-1" and item["days_overdue"] == 3


# ---- create_bill (write) ---------------------------------------------------

@pytest.mark.asyncio
async def test_propose_create_bill_previews_formatted_amount():
    db = MagicMock()
    db.agentaction.create = AsyncMock(return_value=_action(kind="create_bill"))
    from app.core.agent_actions import propose_action
    res = await propose_action(db, "t1", kind="create_bill",
                               params={"vendor": "Acme Ltd", "amount_minor": 12345, "currency": "GBP"},
                               proposed_by="u1")
    assert res["capability"] == "write"
    assert "Acme Ltd" in res["preview"] and "123.45" in res["preview"]
    data = db.agentaction.create.await_args.kwargs["data"]
    assert data["capability"] == "write" and data["params"]["amount_minor"] == 12345


@pytest.mark.asyncio
async def test_propose_create_bill_rejects_nonpositive_amount():
    db = MagicMock()
    db.agentaction.create = AsyncMock()
    from app.core.agent_actions import propose_action, AgentActionError
    with pytest.raises(AgentActionError, match="positive"):
        await propose_action(db, "t1", kind="create_bill",
                             params={"vendor": "Acme", "amount_minor": 0, "currency": "GBP"},
                             proposed_by="u1")
    db.agentaction.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_create_bill_creates_native_bill_and_posts_dry_run():
    action = _action(kind="create_bill",
                     params={"vendor": "Acme Ltd", "amount_minor": 12345, "currency": "GBP",
                             "number": "B-1", "due_date": None})
    db = MagicMock()
    db.agentaction.find_first = AsyncMock(return_value=action)
    db.agentaction.update = AsyncMock()
    db.accountingbill.find_first = AsyncMock(return_value=None)
    created_bill = MagicMock(id="bill1")
    db.accountingbill.create = AsyncMock(return_value=created_bill)
    with (
        patch("app.core.agent_actions.write_audit_log", AsyncMock()) as audit,
        patch("app.core.erp_writer.post_bill", AsyncMock(return_value={"mode": "dry_run"})) as post,
    ):
        from app.core.agent_actions import execute_action
        res = await execute_action(db, "t1", "act1", confirmed_by="u1")
    assert res["executed"] is True
    # native bill written (source="invoice", payable, minor units mirrored)
    db.accountingbill.create.assert_awaited_once()
    bd = db.accountingbill.create.await_args.kwargs["data"]
    assert bd["source"] == "invoice" and bd["status"] == "open"
    assert bd["outstanding_cents"] == 12345 and bd["contact_name"] == "Acme Ltd"
    # posted via the governed rail with the created bill (dry-run unless erp_write_live)
    post.assert_awaited_once()
    assert post.await_args.args[2] is created_bill
    # audit-first: create_bill audit written before mutation, plus the generic execute audit
    assert audit.await_count >= 2


@pytest.mark.asyncio
async def test_execute_create_bill_is_idempotent_on_existing_bill():
    action = _action(kind="create_bill",
                     params={"vendor": "Acme Ltd", "amount_minor": 12345, "currency": "GBP",
                             "number": "B-1", "due_date": None})
    db = MagicMock()
    db.agentaction.find_first = AsyncMock(return_value=action)
    db.agentaction.update = AsyncMock()
    db.accountingbill.find_first = AsyncMock(return_value=MagicMock(id="prior"))
    db.accountingbill.create = AsyncMock()
    with (
        patch("app.core.agent_actions.write_audit_log", AsyncMock()),
        patch("app.core.erp_writer.post_bill", AsyncMock(return_value={"mode": "dry_run"})) as post,
    ):
        from app.core.agent_actions import execute_action
        await execute_action(db, "t1", "act1", confirmed_by="u1")
    db.accountingbill.create.assert_not_awaited()  # reused the existing bill
    post.assert_awaited_once()


@pytest.mark.asyncio
async def test_clen_create_bill_returns_proposal():
    db = MagicMock()
    db.agentaction.create = AsyncMock(return_value=_action(kind="create_bill"))
    from app.clen.tools import execute_tool
    res = await execute_tool("create_bill",
                             {"vendor": "Acme", "amount_minor": 5000, "currency": "GBP"},
                             "t1", "u1", db)
    assert "proposed_action" in res
    assert res["proposed_action"]["kind"] == "create_bill"
