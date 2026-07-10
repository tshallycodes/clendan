"""
Payment preparation + PaymentRun lifecycle.

MONEY-MOVEMENT BOUNDARY (locked principle). Clendan never custodies or transfers funds.
Moving a client's money would make Clendan a money transmitter (licensing / fund
safeguarding) - a different, regulated business. Instead Clendan *prepares* a payment batch
and hands off: the authorised human releases it in the system that already holds the money
(the client's bank / ERP). "Approve" here records that a run was released and marks its bills
paid in Clendan's mirror so the books reflect it - it does NOT wire money.

Deliberately SEPARATE from app/tools/payment_run.py, whose docstring forbids a payout call:
the tool only schedules/records intent. `payments_live` is kept as a hard tripwire - there is
by design NO disbursement rail, so if anyone ever flips it, `_execute_payout` refuses loudly
rather than silently moving funds through unreviewed code.

State machine on PaymentRun.status:
    scheduled  --approve (before scheduled_for)--> paid
    scheduled  --deadline passes (cron)---------->  cancelled
    scheduled / cancelled --reschedule---------->  scheduled (new scheduled_for)
"""
from datetime import UTC, datetime

from prisma import Json

from app.audit.logger import write_audit_log
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_LIFECYCLE_VERSION = "payment_run-lifecycle-v1"


class PaymentRunError(Exception):
    """A lifecycle action is invalid for the run's current state (maps to HTTP 409)."""


async def _mark_bills_paid(db, tenant_id: str, bill_ids: list) -> None:
    now = datetime.now(UTC)
    for bill_id in bill_ids or []:
        try:
            await db.accountingbill.update_many(
                where={"id": bill_id, "tenant_id": tenant_id},
                data={"status": "paid", "outstanding_cents": 0, "paid_at": now},
            )
        except Exception as exc:
            logger.warning("payout_mark_bill_failed bill_id=%s: %s", bill_id, type(exc).__name__)


async def _execute_payout(db, tenant_id: str, run) -> dict:
    """Record a scheduled run as released. Clendan does NOT move money (see the module
    MONEY-MOVEMENT BOUNDARY): it marks the batch's bills paid in Clendan's mirror so the books
    reflect the payment the human is releasing in the bank/ERP. `payments_live` is a tripwire -
    there is deliberately no disbursement rail, so it refuses loudly if ever enabled."""
    settings = get_settings()
    bill_ids = list(run.bill_ids or [])
    if settings.payments_live:
        # By design Clendan prepares payments and hands off - it never transfers funds. This
        # refuses loudly so "live" can never silently wire a client's money.
        raise PaymentRunError(
            "Clendan does not disburse funds (prepare-and-hand-off by design); "
            "payments_live must stay off."
        )
    await _mark_bills_paid(db, tenant_id, bill_ids)
    return {"mode": "dry_run", "bills_paid": len(bill_ids), "total_cents": run.total_amount_cents}


async def approve_payment_run(db, tenant_id: str, run_id: str, actor: str = "user") -> dict:
    """Approve a scheduled run before its deadline and disburse it."""
    run = await db.paymentrun.find_first(where={"id": run_id, "tenant_id": tenant_id})
    if not run:
        raise PaymentRunError("Payment run not found")
    if run.status != "scheduled":
        raise PaymentRunError(f"Run is '{run.status}' - only a scheduled run can be approved")
    now = datetime.now(UTC)
    if run.scheduled_for and run.scheduled_for.replace(tzinfo=UTC) < now:
        raise PaymentRunError("This run's approval window has passed - reschedule it first")

    result = await _execute_payout(db, tenant_id, run)

    await db.paymentrun.update(
        where={"id": run.id},
        data={"status": "paid", "processed_at": now, "result_json": Json(result)},
    )
    await write_audit_log(
        tenant_id=tenant_id, actor=actor, action="payment_run:approved_paid",
        reasoning_trace={"payment_run_id": run.id, "result": result, "mode": result.get("mode")},
        model_version=_LIFECYCLE_VERSION, execution_id=run.execution_id,
    )
    return result


async def cancel_payment_run(db, tenant_id: str, run_id: str, actor: str = "user", reason: str = "cancelled") -> None:
    run = await db.paymentrun.find_first(where={"id": run_id, "tenant_id": tenant_id})
    if not run:
        raise PaymentRunError("Payment run not found")
    if run.status != "scheduled":
        raise PaymentRunError(f"Run is '{run.status}' - only a scheduled run can be cancelled")
    await db.paymentrun.update(where={"id": run.id}, data={"status": "cancelled"})
    await write_audit_log(
        tenant_id=tenant_id, actor=actor, action="payment_run:cancelled",
        reasoning_trace={"payment_run_id": run.id, "reason": reason},
        model_version=_LIFECYCLE_VERSION, execution_id=run.execution_id,
    )


async def reschedule_payment_run(db, tenant_id: str, run_id: str, new_date: datetime, actor: str = "user") -> None:
    """Put a cancelled (or still-scheduled) run back to scheduled with a new deadline."""
    run = await db.paymentrun.find_first(where={"id": run_id, "tenant_id": tenant_id})
    if not run:
        raise PaymentRunError("Payment run not found")
    if run.status not in ("cancelled", "scheduled"):
        raise PaymentRunError(f"Run is '{run.status}' - a paid run cannot be rescheduled")
    await db.paymentrun.update(
        where={"id": run.id},
        data={"status": "scheduled", "scheduled_for": new_date, "processed_at": None},
    )
    await write_audit_log(
        tenant_id=tenant_id, actor=actor, action="payment_run:rescheduled",
        reasoning_trace={"payment_run_id": run.id, "scheduled_for": new_date.isoformat()},
        model_version=_LIFECYCLE_VERSION, execution_id=run.execution_id,
    )


async def expire_due_payment_runs(db) -> int:
    """Cron helper: auto-cancel every scheduled run whose approval window has elapsed.
    Returns the count cancelled."""
    now = datetime.now(UTC)
    due = await db.paymentrun.find_many(
        where={"status": "scheduled", "scheduled_for": {"lt": now}}, take=500,
    )
    for run in due:
        try:
            await cancel_payment_run(
                db, run.tenant_id, run.id, actor="system:payment_expiry",
                reason="approval_window_elapsed",
            )
        except Exception as exc:
            logger.error("payment_run_expire_failed run_id=%s: %s", run.id, type(exc).__name__)
    return len(due)
