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
    m.contact_id = None  # real Prisma rows carry str|None, never a MagicMock
    m.due_date = now - timedelta(days=days_overdue)
    return m


def _db(invoices, config=None, contacts=None):
    db = MagicMock()
    db.tool.find_first = AsyncMock(return_value=MagicMock(config_json=config or {}))
    db.accountinginvoice.find_many = AsyncMock(return_value=invoices)
    db.accountingcontact.find_many = AsyncMock(return_value=contacts or [])
    db.collectionreminder.find_first = AsyncMock(return_value=None)
    db.collectionreminder.create = AsyncMock()
    db.integration.find_first = AsyncMock(return_value=None)
    db.execution.update = AsyncMock()
    return db


def _contact(external_id="Customer-ext", email="c@x.com", name="Customer"):
    m = MagicMock()
    m.external_id = external_id
    m.email = email
    m.name = name
    return m


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


# ---- reminder dispatch ------------------------------------------------------

def _item(action="reminder", requires_approval=False, invoice_id="a", contact_name="Customer", contact_id=None):
    return {
        "invoice_id": invoice_id, "number": f"N-{invoice_id}", "contact_name": contact_name,
        "contact_id": contact_id, "outstanding_cents": 10_000, "currency": "GBP",
        "days_overdue": 3, "action": action, "tier": action, "late_fee_cents": 0,
        "requires_approval": requires_approval,
    }


class TestReminderDispatch:
    @pytest.mark.asyncio
    async def test_dry_run_previews_without_persisting(self):
        db = _db([], contacts=[_contact()])
        with patch("app.tools.accounts_receivable.send_via_mailbox",
                   AsyncMock(return_value={"mode": "dry_run", "channel": "gmail", "message_id": ""})) as send:
            from app.tools.accounts_receivable import _dispatch_auto_reminders
            summary = await _dispatch_auto_reminders(db, "t1", [_item()])
        send.assert_awaited_once()
        assert summary["dry_run"] == 1 and summary["sent"] == 0
        db.collectionreminder.create.assert_not_awaited()  # dry-run never persists

    @pytest.mark.asyncio
    async def test_live_send_persists_reminder_row(self):
        db = _db([], contacts=[_contact()])
        with patch("app.tools.accounts_receivable.send_via_mailbox",
                   AsyncMock(return_value={"mode": "live", "channel": "gmail", "message_id": "m1"})):
            from app.tools.accounts_receivable import _dispatch_auto_reminders
            summary = await _dispatch_auto_reminders(db, "t1", [_item()])
        assert summary["sent"] == 1
        db.collectionreminder.create.assert_awaited_once()
        data = db.collectionreminder.create.await_args.kwargs["data"]
        assert data["mode"] == "live" and data["tier"] == "reminder" and data["message_id"] == "m1"

    @pytest.mark.asyncio
    async def test_no_email_skips_without_sending(self):
        db = _db([], contacts=[])  # no contact emails available
        with patch("app.tools.accounts_receivable.send_via_mailbox", AsyncMock()) as send:
            from app.tools.accounts_receivable import _dispatch_auto_reminders
            summary = await _dispatch_auto_reminders(db, "t1", [_item()])
        send.assert_not_awaited()
        assert summary["skipped_no_email"] == 1

    @pytest.mark.asyncio
    async def test_dedup_skips_already_live_sent(self):
        db = _db([], contacts=[_contact()])
        db.collectionreminder.find_first = AsyncMock(return_value=MagicMock())  # a live row exists
        with patch("app.tools.accounts_receivable.send_via_mailbox", AsyncMock()) as send:
            from app.tools.accounts_receivable import _dispatch_auto_reminders
            summary = await _dispatch_auto_reminders(db, "t1", [_item()])
        send.assert_not_awaited()
        assert summary["skipped_already_sent"] == 1

    @pytest.mark.asyncio
    async def test_firmer_and_flagged_actions_not_auto_sent(self):
        db = _db([], contacts=[_contact()])
        with patch("app.tools.accounts_receivable.send_via_mailbox", AsyncMock()) as send:
            from app.tools.accounts_receivable import _dispatch_auto_reminders
            summary = await _dispatch_auto_reminders(db, "t1", [
                _item(action="final_notice", requires_approval=True),
                _item(action="reminder", requires_approval=True),  # reminder tier but routed to approval
            ])
        send.assert_not_awaited()
        assert summary["sent"] == 0 and summary["dry_run"] == 0

    @pytest.mark.asyncio
    async def test_mail_error_recorded_as_failed(self):
        from app.core.mailer import MailError
        db = _db([], contacts=[_contact()])
        with patch("app.tools.accounts_receivable.send_via_mailbox",
                   AsyncMock(side_effect=MailError("no mailbox"))):
            from app.tools.accounts_receivable import _dispatch_auto_reminders
            summary = await _dispatch_auto_reminders(db, "t1", [_item()])
        assert summary["failed"] == 1
        db.collectionreminder.create.assert_not_awaited()
