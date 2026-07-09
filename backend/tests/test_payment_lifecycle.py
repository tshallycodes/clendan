"""
Tests for the PaymentRun lifecycle + dry-run disbursement (app/core/payouts.py).
No DB - the Prisma client, settings, and audit log are mocked.
"""
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _run(status="scheduled", scheduled_for=None, bill_ids=None):
    r = MagicMock()
    r.id = "run1"
    r.tenant_id = "t1"
    r.execution_id = "e1"
    r.status = status
    r.scheduled_for = scheduled_for
    r.bill_ids = bill_ids if bill_ids is not None else ["b1", "b2"]
    r.total_amount_cents = 5000
    return r


def _db(run):
    db = MagicMock()
    db.paymentrun.find_first = AsyncMock(return_value=run)
    db.paymentrun.update = AsyncMock()
    db.paymentrun.find_many = AsyncMock(return_value=[run] if run else [])
    db.accountingbill.update_many = AsyncMock()
    return db


def _settings(live=False):
    s = MagicMock()
    s.payments_live = live
    return s


@pytest.mark.asyncio
async def test_approve_dry_run_marks_bills_paid():
    run = _run(scheduled_for=datetime.now(UTC) + timedelta(days=2))
    db = _db(run)
    with (
        patch("app.core.payouts.get_settings", return_value=_settings(False)),
        patch("app.core.payouts.write_audit_log", AsyncMock()),
    ):
        from app.core.payouts import approve_payment_run
        result = await approve_payment_run(db, "t1", "run1")
    assert result["mode"] == "dry_run"
    assert result["bills_paid"] == 2
    assert db.accountingbill.update_many.await_count == 2  # each bill marked paid
    assert db.paymentrun.update.await_args.kwargs["data"]["status"] == "paid"


@pytest.mark.asyncio
async def test_approve_past_deadline_refused():
    run = _run(scheduled_for=datetime.now(UTC) - timedelta(hours=1))
    db = _db(run)
    with (
        patch("app.core.payouts.get_settings", return_value=_settings(False)),
        patch("app.core.payouts.write_audit_log", AsyncMock()),
    ):
        from app.core.payouts import approve_payment_run, PaymentRunError
        with pytest.raises(PaymentRunError, match="window has passed"):
            await approve_payment_run(db, "t1", "run1")
    db.accountingbill.update_many.assert_not_awaited()


@pytest.mark.asyncio
async def test_approve_only_scheduled():
    db = _db(_run(status="paid"))
    with patch("app.core.payouts.write_audit_log", AsyncMock()):
        from app.core.payouts import approve_payment_run, PaymentRunError
        with pytest.raises(PaymentRunError):
            await approve_payment_run(db, "t1", "run1")


@pytest.mark.asyncio
async def test_live_payout_refuses_without_rail():
    run = _run(scheduled_for=datetime.now(UTC) + timedelta(days=2))
    db = _db(run)
    with (
        patch("app.core.payouts.get_settings", return_value=_settings(True)),
        patch("app.core.payouts.write_audit_log", AsyncMock()),
    ):
        from app.core.payouts import approve_payment_run, PaymentRunError
        with pytest.raises(PaymentRunError, match="no payout rail"):
            await approve_payment_run(db, "t1", "run1")
    db.accountingbill.update_many.assert_not_awaited()  # nothing marked paid when it refuses


@pytest.mark.asyncio
async def test_cancel_scheduled():
    db = _db(_run())
    with patch("app.core.payouts.write_audit_log", AsyncMock()):
        from app.core.payouts import cancel_payment_run
        await cancel_payment_run(db, "t1", "run1")
    assert db.paymentrun.update.await_args.kwargs["data"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_reschedule_from_cancelled():
    db = _db(_run(status="cancelled"))
    new = datetime.now(UTC) + timedelta(days=5)
    with patch("app.core.payouts.write_audit_log", AsyncMock()):
        from app.core.payouts import reschedule_payment_run
        await reschedule_payment_run(db, "t1", "run1", new)
    data = db.paymentrun.update.await_args.kwargs["data"]
    assert data["status"] == "scheduled"
    assert data["scheduled_for"] == new


@pytest.mark.asyncio
async def test_reschedule_paid_refused():
    db = _db(_run(status="paid"))
    with patch("app.core.payouts.write_audit_log", AsyncMock()):
        from app.core.payouts import reschedule_payment_run, PaymentRunError
        with pytest.raises(PaymentRunError):
            await reschedule_payment_run(db, "t1", "run1", datetime.now(UTC) + timedelta(days=1))


@pytest.mark.asyncio
async def test_expire_due_cancels_past_deadline():
    db = _db(_run(scheduled_for=datetime.now(UTC) - timedelta(hours=1)))
    with patch("app.core.payouts.write_audit_log", AsyncMock()):
        from app.core.payouts import expire_due_payment_runs
        n = await expire_due_payment_runs(db)
    assert n == 1
    assert db.paymentrun.update.await_args.kwargs["data"]["status"] == "cancelled"
