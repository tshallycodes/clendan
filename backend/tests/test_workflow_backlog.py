"""
Tests for the per-connection backlog counter (app/api/v1/workflows._edge_backlog):
how many records processed upstream are still waiting for the downstream tool.
No DB - the Prisma client is mocked.
"""
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest


def _tool(tid):
    m = MagicMock()
    m.id = tid
    return m


def _exec(created_at):
    m = MagicMock()
    m.created_at = created_at
    m.decision = "auto_approved"
    return m


def _db(bills_count=0, exp_count=0, approved=None, runs=None, spend_cfg=None):
    db = MagicMock()
    db.accountingbill.count = AsyncMock(return_value=bills_count)
    db.accountingexpense.count = AsyncMock(return_value=exp_count)
    db.accountingbill.find_many = AsyncMock(return_value=approved or [])
    db.paymentrun.find_many = AsyncMock(return_value=runs or [])
    db.tool.find_first = AsyncMock(return_value=MagicMock(config_json=spend_cfg or {}))
    return db


@pytest.mark.asyncio
async def test_doc_intel_to_spend_backlog_sums_unassessed_bills_and_expenses():
    from app.api.v1.workflows import _edge_backlog
    db = _db(bills_count=5, exp_count=3)
    n = await _edge_backlog(db, "t1", "document_intelligence", "spend_control")
    assert n == 8
    # backlog = records Spend Control has not assessed yet (control_status unset)
    assert db.accountingbill.count.await_args.kwargs["where"]["control_status"] is None
    exp_where = db.accountingexpense.count.await_args.kwargs["where"]
    assert exp_where["control_status"] is None
    assert "expense_date" not in exp_where  # default (0) = no age limit, sweeps all unassessed


@pytest.mark.asyncio
async def test_doc_intel_expense_backlog_respects_catch_up_limit():
    from app.api.v1.workflows import _edge_backlog
    db = _db(bills_count=2, exp_count=4, spend_cfg={"expense_lookback_days": 60})
    n = await _edge_backlog(db, "t1", "document_intelligence", "spend_control")
    assert n == 6
    # a positive catch-up limit bounds the expense count by expense_date
    assert "expense_date" in db.accountingexpense.count.await_args.kwargs["where"]


@pytest.mark.asyncio
async def test_spend_to_payment_backlog_excludes_bills_already_in_a_run():
    from app.api.v1.workflows import _edge_backlog
    approved = [MagicMock(id="b1"), MagicMock(id="b2"), MagicMock(id="b3")]
    runs = [MagicMock(bill_ids=["b1"]), MagicMock(bill_ids=["b2"])]  # b1, b2 already scheduled/paid
    db = _db(approved=approved, runs=runs)
    n = await _edge_backlog(db, "t1", "spend_control", "payment_run")
    assert n == 1  # only b3 is still waiting for a payment run


@pytest.mark.asyncio
async def test_spend_to_payment_backlog_zero_short_circuits():
    from app.api.v1.workflows import _edge_backlog
    db = _db(approved=[])
    n = await _edge_backlog(db, "t1", "spend_control", "payment_run")
    assert n == 0
    db.paymentrun.find_many.assert_not_awaited()  # no approved bills -> don't scan runs


@pytest.mark.asyncio
async def test_window_based_edges_have_no_backlog():
    from app.api.v1.workflows import _edge_backlog
    db = _db()
    assert await _edge_backlog(db, "t1", "reconciliation", "tax_compliance") is None
    assert await _edge_backlog(db, "t1", "tax_compliance", "financial_reporting") is None


# ---- staleness (the flush signal for window-based close edges) --------------

@pytest.mark.asyncio
async def test_stale_when_downstream_never_ran():
    from app.api.v1.workflows import _edge_stale
    db = MagicMock()
    db.execution.find_first = AsyncMock(side_effect=[_exec(datetime(2026, 7, 1, tzinfo=UTC)), None])
    assert await _edge_stale(db, "t1", _tool("up"), _tool("down")) is True


@pytest.mark.asyncio
async def test_stale_when_upstream_ran_more_recently():
    from app.api.v1.workflows import _edge_stale
    db = MagicMock()
    db.execution.find_first = AsyncMock(side_effect=[
        _exec(datetime(2026, 7, 2, tzinfo=UTC)),  # upstream newer
        _exec(datetime(2026, 7, 1, tzinfo=UTC)),  # downstream older
    ])
    assert await _edge_stale(db, "t1", _tool("up"), _tool("down")) is True


@pytest.mark.asyncio
async def test_not_stale_when_downstream_current():
    from app.api.v1.workflows import _edge_stale
    db = MagicMock()
    db.execution.find_first = AsyncMock(side_effect=[
        _exec(datetime(2026, 7, 1, tzinfo=UTC)),
        _exec(datetime(2026, 7, 2, tzinfo=UTC)),  # downstream ran after upstream
    ])
    assert await _edge_stale(db, "t1", _tool("up"), _tool("down")) is False


@pytest.mark.asyncio
async def test_not_stale_when_upstream_never_ran():
    from app.api.v1.workflows import _edge_stale
    db = MagicMock()
    db.execution.find_first = AsyncMock(return_value=None)
    assert await _edge_stale(db, "t1", _tool("up"), _tool("down")) is False


@pytest.mark.asyncio
async def test_not_stale_when_a_tool_is_undeployed():
    from app.api.v1.workflows import _edge_stale
    db = MagicMock()
    db.execution.find_first = AsyncMock()
    assert await _edge_stale(db, "t1", None, _tool("down")) is False
    db.execution.find_first.assert_not_awaited()
