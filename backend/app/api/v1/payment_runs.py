"""Payment run batch routes — list and cancel scheduled PaymentRun batches.

Creating a batch is done by triggering the payment_run tool (POST /tools/{id}/run),
which schedules/records intent only. Actual disbursement is intentionally gated —
no money-movement happens here. A scheduled batch can be cancelled before processing.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from prisma import Prisma

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import CurrentUser, RequireOrgAuth, require_role

logger = get_logger(__name__)
router = APIRouter(prefix="/payment-runs", tags=["payment-runs"])


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
        "created_at": run.created_at.isoformat(),
    }


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


@router.patch("/{run_id}/cancel")
async def cancel_payment_run(
    run_id: str,
    current_user: Annotated[CurrentUser, require_role("owner", "admin", "approver")],
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Cancel a scheduled payment run before it is processed. Tenant-scoped."""
    run = await db.paymentrun.find_first(
        where={"id": run_id, "tenant_id": current_user.tenant_id}
    )
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment run not found")
    if run.status != "scheduled":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only scheduled runs can be cancelled (this one is '{run.status}')",
        )

    updated = await db.paymentrun.update(where={"id": run_id}, data={"status": "cancelled"})
    logger.info("payment_run_cancelled", extra={"run_id": run_id, "tenant_id": current_user.tenant_id})
    return standard_response(data=_serialize(updated))
