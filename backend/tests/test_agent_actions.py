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
