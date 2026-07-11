"""Report pull-through routes - read the connected ERP's authoritative P&L / balance-sheet /
VAT figures (operate their numbers, don't re-derive them). Returns {available: false, ...}
when no report-capable accounting integration is connected, so callers fall back gracefully.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma

from app.core.db import get_db_dep
from app.core.erp_reports import fetch_report
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth

logger = get_logger(__name__)
router = APIRouter(prefix="/reports", tags=["reports"])


async def _report(report_type: str, current_user, db: Prisma):
    try:
        report = await fetch_report(db, current_user.tenant_id, report_type)
    except Exception as exc:  # noqa: BLE001 - never leak a raw ERP/HTTP error to the client
        logger.error(
            "erp_report_fetch_failed type=%s tenant=%s error=%s",
            report_type, current_user.tenant_id, type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not fetch the report from the connected accounting system",
        )
    if report is None:
        return standard_response(data={
            "available": False, "report_type": report_type,
            "reason": "no report-capable accounting integration connected",
        })
    return standard_response(data={"available": True, **report})


@router.get("/pnl")
async def get_pnl(current_user: RequireOrgAuth, db: Annotated[Prisma, Depends(get_db_dep)]):
    """Profit & loss from the connected ERP."""
    return await _report("pnl", current_user, db)


@router.get("/balance-sheet")
async def get_balance_sheet(current_user: RequireOrgAuth, db: Annotated[Prisma, Depends(get_db_dep)]):
    """Balance sheet from the connected ERP."""
    return await _report("balance_sheet", current_user, db)


@router.get("/vat")
async def get_vat(current_user: RequireOrgAuth, db: Annotated[Prisma, Depends(get_db_dep)]):
    """VAT report from the connected ERP (QuickBooks only; Xero VAT isn't a Reports endpoint)."""
    return await _report("vat", current_user, db)
