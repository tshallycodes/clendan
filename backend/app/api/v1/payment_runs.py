"""Payment run lifecycle routes - list, approve (disburse), cancel, reschedule.

Creating a batch is done by triggering the payment_run tool (POST /tools/{id}/run), which
schedules/records intent only. The state machine and the (dry-run by default) disbursement
live in app/core/payouts.py:

    scheduled --approve (before deadline)--> paid
    scheduled --deadline passes (cron)-----> cancelled
    scheduled / cancelled --reschedule-----> scheduled
"""
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from prisma import Prisma
from pydantic import BaseModel

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.payouts import (
    PaymentRunError,
    approve_payment_run,
    reschedule_payment_run,
)
from app.core.payouts import cancel_payment_run as _cancel_run
from app.core.responses import standard_response
from app.core.security import CurrentUser, RequireOrgAuth, require_role

logger = get_logger(__name__)
router = APIRouter(prefix="/payment-runs", tags=["payment-runs"])

# Money actions are gated to finance roles.
FinanceUser = Annotated[CurrentUser, require_role("owner", "admin", "approver")]


class RescheduleRequest(BaseModel):
    scheduled_for: str  # ISO date/datetime


def _serialize(run) -> dict:
    bill_ids = run.bill_ids if isinstance(run.bill_ids, list) else []
    return {
        "id": run.id,
        "status": run.status,
        "scheduled_for": run.scheduled_for.isoformat() if run.scheduled_for else None,
        "processed_at": run.processed_at.isoformat() if run.processed_at else None,
        "bill_count": run.bill_count,
        "total_amount_cents": run.total_amount_cents,
        "currency": run.currency,
        "bill_ids": bill_ids,
        "result": run.result_json,
        "created_at": run.created_at.isoformat(),
    }


def _raise_lifecycle(exc: PaymentRunError):
    code = status.HTTP_404_NOT_FOUND if "not found" in str(exc).lower() else status.HTTP_409_CONFLICT
    raise HTTPException(status_code=code, detail=str(exc))


async def _reload(db, tenant_id: str, run_id: str) -> dict:
    run = await db.paymentrun.find_first(where={"id": run_id, "tenant_id": tenant_id})
    return _serialize(run) if run else {}


@router.get("")
async def list_payment_runs(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List the tenant's payment run batches, newest first."""
    runs = await db.paymentrun.find_many(
        where={"tenant_id": current_user.tenant_id},
        order={"created_at": "desc"},
        take=limit,
        skip=offset,
    )
    return standard_response(data={"runs": [_serialize(r) for r in runs]})


@router.patch("/{run_id}/approve")
async def approve_run(
    run_id: str,
    current_user: FinanceUser,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Approve a scheduled run before its deadline and disburse it (dry-run unless live
    payouts are configured)."""
    try:
        result = await approve_payment_run(
            db, current_user.tenant_id, run_id, actor=f"user:{current_user.user_id}",
        )
    except PaymentRunError as exc:
        _raise_lifecycle(exc)
    data = await _reload(db, current_user.tenant_id, run_id)
    data["result"] = result
    return standard_response(data=data)


@router.patch("/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    current_user: FinanceUser,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Cancel a scheduled payment run before it is disbursed."""
    try:
        await _cancel_run(db, current_user.tenant_id, run_id, actor=f"user:{current_user.user_id}")
    except PaymentRunError as exc:
        _raise_lifecycle(exc)
    return standard_response(data=await _reload(db, current_user.tenant_id, run_id))


@router.patch("/{run_id}/reschedule")
async def reschedule_run(
    run_id: str,
    body: RescheduleRequest,
    current_user: FinanceUser,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Put a cancelled (or still-scheduled) run back to scheduled with a new deadline."""
    try:
        parsed = datetime.fromisoformat(body.scheduled_for)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid scheduled_for date")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    if parsed <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reschedule date must be in the future")
    try:
        await reschedule_payment_run(db, current_user.tenant_id, run_id, parsed, actor=f"user:{current_user.user_id}")
    except PaymentRunError as exc:
        _raise_lifecycle(exc)
    return standard_response(data=await _reload(db, current_user.tenant_id, run_id))
