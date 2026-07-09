"""
Payment disbursement + PaymentRun lifecycle.

Deliberately SEPARATE from app/tools/payment_run.py, whose docstring forbids a payout call:
the tool only schedules/records intent. This is the gated place where money actually moves -
and by default it does NOT. `_execute_payout` runs in dry-run mode (marks the batch's bills
paid in Clendan, no money moves) unless settings.payments_live is true, in which case a real
payout rail must be wired. The rail is intentionally a refusing stub until a provider +
credentials + a go-live review land - so "live" can never silently mean "nothing happened".

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
    """Disburse a scheduled run. DRY-RUN by default: marks the batch's bills paid in Clendan
    without moving money. Real money moves only when payments_live is on AND a rail is wired
    (currently a refusing stub)."""
    settings = get_settings()
    bill_ids = list(run.bill_ids or [])
    if settings.payments_live:
        # Real disbursement rail goes here (Wise / bank / provider) with idempotency keys,
        # retries with backoff, and a reconciliation follow-up. Intentionally refuses rather
        # than silently no-op, so enabling "live" without a rail fails loudly.
        raise PaymentRunError("Live payouts are enabled but no payout rail is configured.")
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
