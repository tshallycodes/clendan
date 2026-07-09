"""
Tests for the AR & Collections tool: aging tiers, the not-yet-due guard, and the
approval routing decision. No DB - the Prisma client and audit log are mocked.
"""
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---- pure aging logic -------------------------------------------------------

def test_tier_for_ladder():
    from app.tools.accounts_receivable import _tier_for, _ToolPolicy
    p = _ToolPolicy()  # reminder_1=0, reminder_2=7, final=14, escalate=30, write_off=120
    assert _tier_for(0, p)[0] == "reminder"
    assert _tier_for(7, p)[0] == "second_reminder"
    assert _tier_for(14, p)[0] == "final_notice"
    assert _tier_for(30, p)[0] == "escalate"
    assert _tier_for(120, p)[0] == "write_off_candidate"


def test_not_yet_due_is_no_action():
    """An invoice due in the future must not trigger a reminder."""
    from app.tools.accounts_receivable import _tier_for, _days_overdue, _ToolPolicy
    now = datetime(2026, 7, 9, tzinfo=UTC)
    future = now + timedelta(days=10)
    days = _days_overdue(future, now)
    assert days == -10
    assert _tier_for(days, _ToolPolicy())[0] == "none"


def test_days_overdue_none_when_no_due_date():
    from app.tools.accounts_receivable import _days_overdue
    assert _days_overdue(None, datetime.now(UTC)) is None


# ---- decision routing -------------------------------------------------------

def _inv(inv_id: str, outstanding_cents: int, days_overdue: int, status: str = "authorised"):
    now = datetime.now(UTC)
    m = MagicMock()
    m.id = inv_id
    m.outstanding_cents = outstanding_cents
    m.status = status
    m.currency = "GBP"
    m.number = f"N-{inv_id}"
    m.contact_name = "Customer"
    m.due_date = now - timedelta(days=days_overdue)
    return m


def _db(invoices, config=None):
    db = MagicMock()
    db.tool.find_first = AsyncMock(return_value=MagicMock(config_json=config or {}))
    db.accountinginvoice.find_many = AsyncMock(return_value=invoices)
    db.execution.update = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_only_reminders_auto_approves():
    db = _db([_inv("a", 10_000, days_overdue=2)])  # 2 days overdue -> reminder tier
    with (
        patch("app.tools.accounts_receivable.get_db", return_value=db),
        patch("app.tools.accounts_receivable.write_audit_log", AsyncMock()),
    ):
        from app.tools.accounts_receivable import _execute
        result = await _execute("t1", "tool1", "e1", {})
    assert result["decision"] == "auto_approved"
    assert result["output_data"]["action_count"] == 1


@pytest.mark.asyncio
async def test_final_notice_requires_approval():
    db = _db([_inv("a", 10_000, days_overdue=20)])  # 20 days -> final_notice -> approval
    with (
        patch("app.tools.accounts_receivable.get_db", return_value=db),
        patch("app.tools.accounts_receivable.write_audit_log", AsyncMock()),
    ):
        from app.tools.accounts_receivable import _execute
        result = await _execute("t1", "tool1", "e1", {})
    assert result["decision"] == "approval_required"


@pytest.mark.asyncio
async def test_reminders_route_for_approval_when_auto_send_off():
    db = _db([_inv("a", 10_000, days_overdue=2)], config={"auto_send_reminders": False})
    with (
        patch("app.tools.accounts_receivable.get_db", return_value=db),
        patch("app.tools.accounts_receivable.write_audit_log", AsyncMock()),
    ):
        from app.tools.accounts_receivable import _execute
        result = await _execute("t1", "tool1", "e1", {})
    assert result["decision"] == "approval_required"


@pytest.mark.asyncio
async def test_paid_invoices_excluded():
    db = _db([_inv("a", 10_000, days_overdue=40, status="paid")])
    with (
        patch("app.tools.accounts_receivable.get_db", return_value=db),
        patch("app.tools.accounts_receivable.write_audit_log", AsyncMock()) as audit,
    ):
        from app.tools.accounts_receivable import _execute
        result = await _execute("t1", "tool1", "e1", {})
    assert result["output_data"] == {"outstanding_count": 0}
    assert result["decision"] == "auto_approved"
    assert audit.await_args.kwargs["action"] == "ar_collections:no_action"


@pytest.mark.asyncio
async def test_late_fee_forces_approval_and_is_computed():
    db = _db(
        [_inv("a", 100_000, days_overdue=35)],
        config={"late_fee_percent": 10, "late_fee_after_days": 30},
    )
    with (
        patch("app.tools.accounts_receivable.get_db", return_value=db),
        patch("app.tools.accounts_receivable.write_audit_log", AsyncMock()),
    ):
        from app.tools.accounts_receivable import _execute
        result = await _execute("t1", "tool1", "e1", {})
    assert result["decision"] == "approval_required"
    assert result["output_data"]["late_fee_cents_total"] == 10_000  # 10% of 100_000
