"""
Reconciliation API — /v1/reconciliation/*
Endpoints: list runs, run items, trigger run, export CSV.
All queries scoped to current_user.tenant_id (no cross-tenant access).
"""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.db import get_db
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth

router = APIRouter(tags=["reconciliation"])


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------


class TriggerRunRequest(BaseModel):
    period_start: str   # ISO datetime string
    period_end: str     # ISO datetime string
    tool_id: str


# ---------------------------------------------------------------------------
# GET /v1/reconciliation/runs
# ---------------------------------------------------------------------------


@router.get("/reconciliation/runs")
async def list_reconciliation_runs(
    current_user: RequireOrgAuth,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """List reconciliation runs for the tenant, newest first."""
    db = get_db()
    tenant_id = current_user.tenant_id

    runs = await db.reconciliationrun.find_many(
        where={"tenant_id": tenant_id},
        order={"created_at": "desc"},
        take=limit,
        skip=offset,
    )
    total = await db.reconciliationrun.count(where={"tenant_id": tenant_id})

    runs_out = [
        {
            "id": r.id,
            "execution_id": r.execution_id,
            "period_start": r.period_start.isoformat(),
            "period_end": r.period_end.isoformat(),
            "status": r.status,
            "matched_count": r.matched_count,
            "unmatched_count": r.unmatched_count,
            "flagged_count": r.flagged_count,
            "review_count": r.review_count,
            "total_txn_count": r.total_txn_count,
            "total_inv_count": r.total_inv_count,
            "created_at": r.created_at.isoformat(),
        }
        for r in runs
    ]

    return standard_response(data={"runs": runs_out, "total": total})


# ---------------------------------------------------------------------------
# GET /v1/reconciliation/runs/{run_id}/items
# ---------------------------------------------------------------------------


@router.get("/reconciliation/runs/{run_id}/items")
async def get_run_items(
    run_id: str,
    current_user: RequireOrgAuth,
    account_id: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    """Return bank transactions for the run's period with match details."""
    db = get_db()
    tenant_id = current_user.tenant_id

    run = await db.reconciliationrun.find_first(
        where={"id": run_id, "tenant_id": tenant_id}
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Reconciliation run not found")

    # Build reasoning lookup from run's details_json
    reasoning_lookup: dict[str, str] = {}
    if run.details_json and isinstance(run.details_json, dict):
        for assessment in run.details_json.get("claude_assessments", []):
            item_id = assessment.get("item_id")
            if item_id:
                reasoning_lookup[item_id] = assessment.get("reasoning", "")

    txn_where: dict = {
        "tenant_id": tenant_id,
        "date": {"gte": run.period_start, "lte": run.period_end},
    }
    if account_id:
        txn_where["account_id"] = account_id
    if status:
        txn_where["status"] = status

    txns = await db.banktransaction.find_many(
        where=txn_where,
        include={"account": True, "matched_invoice": True},
        order={"date": "desc"},
    )

    items = [
        {
            "id": t.id,
            "date": t.date.isoformat(),
            "account_name": t.account.name if t.account else None,
            "account_id": t.account_id,
            "description": t.description,
            "merchant_name": t.merchant_name,
            "amount_minor": t.amount_minor,
            "currency": t.currency,
            "status": t.status,
            "matched_invoice_number": (
                t.matched_invoice.invoice_number if t.matched_invoice else None
            ),
            "matched_vendor": (
                t.matched_invoice.vendor if t.matched_invoice else None
            ),
            "reasoning": reasoning_lookup.get(t.id, ""),
        }
        for t in txns
    ]

    return standard_response(data={"items": items, "total": len(items)})


# ---------------------------------------------------------------------------
# POST /v1/reconciliation/run
# ---------------------------------------------------------------------------


@router.post("/reconciliation/run")
async def trigger_reconciliation_run(
    body: TriggerRunRequest,
    current_user: RequireOrgAuth,
) -> dict:
    """Trigger a reconciliation run. Enqueued asynchronously — poll GET /v1/reconciliation/runs for results."""
    db = get_db()
    tenant_id = current_user.tenant_id

    try:
        period_start = datetime.fromisoformat(body.period_start)
        period_end = datetime.fromisoformat(body.period_end)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid date format: {exc}") from exc

    tool = await db.tool.find_first(
        where={"id": body.tool_id, "tenant_id": tenant_id}
    )
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")

    execution = await db.execution.create(data={
        "tenant_id": tenant_id,
        "tool_id": body.tool_id,
        "input_ref": f"manual:{period_start.date()}:{period_end.date()}",
        "decision": "pending",
        "confidence": 0.0,
        "status": "queued",
    })

    from app.queue.pool import get_queue_pool
    pool = await get_queue_pool()
    await pool.enqueue_job(
        "run_reconciliation_job",
        execution_id=execution.id,
        tenant_id=tenant_id,
        tool_id=body.tool_id,
        period_start=period_start,
        period_end=period_end,
    )

    return standard_response(data={
        "execution_id": execution.id,
        "status": "queued",
    })


# ---------------------------------------------------------------------------
# GET /v1/reconciliation/runs/{run_id}/export
# ---------------------------------------------------------------------------


@router.get("/reconciliation/runs/{run_id}/export")
async def export_run_csv(
    run_id: str,
    current_user: RequireOrgAuth,
) -> StreamingResponse:
    """Export all items for a reconciliation run as CSV."""
    db = get_db()
    tenant_id = current_user.tenant_id

    run = await db.reconciliationrun.find_first(
        where={"id": run_id, "tenant_id": tenant_id}
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Reconciliation run not found")

    reasoning_lookup: dict[str, str] = {}
    if run.details_json and isinstance(run.details_json, dict):
        for assessment in run.details_json.get("claude_assessments", []):
            item_id = assessment.get("item_id")
            if item_id:
                reasoning_lookup[item_id] = assessment.get("reasoning", "")

    txns = await db.banktransaction.find_many(
        where={
            "tenant_id": tenant_id,
            "date": {"gte": run.period_start, "lte": run.period_end},
        },
        include={"account": True, "matched_invoice": True},
        order={"date": "desc"},
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "date", "account_name", "description", "merchant_name",
        "amount", "currency", "status", "matched_invoice_number",
        "matched_vendor", "reasoning",
    ])

    for t in txns:
        writer.writerow([
            t.date.isoformat(),
            t.account.name if t.account else "",
            t.description or "",
            t.merchant_name or "",
            f"{t.amount_minor / 100:.2f}",
            t.currency,
            t.status,
            t.matched_invoice.invoice_number if t.matched_invoice else "",
            t.matched_invoice.vendor if t.matched_invoice else "",
            reasoning_lookup.get(t.id, ""),
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=\"reconciliation_{run_id}.csv\""},
    )
