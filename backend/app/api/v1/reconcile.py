"""
Reconciliation API — /v1/reconciliation/* and /v1/reconcile (inline stub).
Endpoints: list runs, run items, trigger run, export CSV, inline dataset compare.
All queries scoped to current_user.tenant_id (no cross-tenant access).
"""
from __future__ import annotations

import asyncio
import csv
import io
import uuid
from datetime import UTC, datetime, timedelta
from typing import Optional

from fastapi import HTTPException, Query
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
    account_ids: Optional[list[str]] = None
    integration_sources: Optional[list[str]] = None


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
            "triggered_by_email": r.triggered_by_email,
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

    # Build reasoning + action lookups from run's details_json
    reasoning_lookup: dict[str, str] = {}
    action_lookup: dict[str, str] = {}
    severity_lookup: dict[str, str] = {}
    if run.details_json and isinstance(run.details_json, dict):
        for assessment in run.details_json.get("claude_assessments", []):
            item_id = assessment.get("item_id")
            if item_id:
                reasoning_lookup[item_id] = assessment.get("reasoning", "")
                action_lookup[item_id] = assessment.get("action", "")
                severity_lookup[item_id] = assessment.get("severity", "")

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
        include={"account": True, "matched_invoice": True, "matched_bill": True},
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
            "ai_action": action_lookup.get(t.id) or None,
            "ai_severity": severity_lookup.get(t.id) or None,
            "matched_invoice_number": (
                t.matched_invoice.invoice_number if t.matched_invoice else None
            ),
            "matched_vendor": (
                t.matched_invoice.vendor if t.matched_invoice
                else (t.matched_bill.contact_name if t.matched_bill else None)
            ),
            "matched_source": (
                t.matched_invoice.source if t.matched_invoice
                else (t.matched_bill.source if t.matched_bill else None)
            ),
            "reasoning": reasoning_lookup.get(t.id, ""),
        }
        for t in txns
    ]

    return standard_response(data={"items": items, "total": len(items)})


# ---------------------------------------------------------------------------
# GET /v1/reconciliation/accounts
# ---------------------------------------------------------------------------


@router.get("/reconciliation/accounts")
async def list_reconciliation_accounts(current_user: RequireOrgAuth) -> dict:
    """Returns all bank accounts for the tenant across all providers, for the run filter."""
    db = get_db()
    accounts = await db.bankaccount.find_many(
        where={"tenant_id": current_user.tenant_id},
        order={"created_at": "asc"},
    )
    return standard_response(data={
        "accounts": [
            {
                "id": a.id,
                "name": a.name,
                "subtype": a.subtype or "",
                "source": a.source,
            }
            for a in accounts
        ]
    })


# ---------------------------------------------------------------------------
# GET /v1/reconciliation/integrations
# ---------------------------------------------------------------------------


@router.get("/reconciliation/integrations")
async def list_reconciliation_integrations(current_user: RequireOrgAuth) -> dict:
    """Returns integration sources that are genuinely connected for this tenant."""
    db = get_db()
    tenant_id = current_user.tenant_id

    _ACCOUNTING_TYPES = {"xero", "quickbooks", "freshbooks", "sage"}

    accounts, connected = await asyncio.gather(
        db.bankaccount.find_many(where={"tenant_id": tenant_id}),
        db.integration.find_many(
            where={"tenant_id": tenant_id, "status": {"in": ["connected", "syncing"]}}
        ),
    )

    bank_sources = sorted({a.source for a in accounts if a.source})
    accounting_sources = sorted({i.type for i in connected if i.type in _ACCOUNTING_TYPES})

    return standard_response(data={
        "bank_sources": bank_sources,
        "accounting_sources": accounting_sources,
    })


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

    if period_start >= period_end:
        raise HTTPException(status_code=422, detail="period_start must be before period_end")

    _stale_cutoff = datetime.now(UTC) - timedelta(minutes=30)
    in_flight = await db.execution.find_first(
        where={"tenant_id": tenant_id, "tool_id": body.tool_id, "status": {"in": ["queued", "running"]}}
    )
    if in_flight:
        if in_flight.created_at.replace(tzinfo=UTC) >= _stale_cutoff:
            raise HTTPException(status_code=409, detail="A reconciliation run is already in progress")
        # Execution stuck for >30 min — mark failed so the new run can proceed
        await db.execution.update(
            where={"id": in_flight.id},
            data={"status": "failed", "decision": "failed", "error_message": "Timed out — marked failed by new run trigger"},
        )

    tool = await db.tool.find_first(
        where={"id": body.tool_id, "tenant_id": tenant_id}
    )
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")

    execution = await db.execution.create(data={
        "tenant_id": tenant_id,
        "tool_id": body.tool_id,
        "input_ref": f"manual:{period_start.date()}:{period_end.date()}:{uuid.uuid4().hex[:8]}",
        "decision": "pending",
        "confidence": 0.0,
        "status": "queued",
        "triggered_by_email": current_user.email,
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
        account_ids=body.account_ids,
        integration_sources=body.integration_sources,
        triggered_by_email=current_user.email,
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
    display_currency: str | None = Query(None),
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
    action_lookup_csv: dict[str, str] = {}
    if run.details_json and isinstance(run.details_json, dict):
        for assessment in run.details_json.get("claude_assessments", []):
            item_id = assessment.get("item_id")
            if item_id:
                reasoning_lookup[item_id] = assessment.get("reasoning", "")
                action_lookup_csv[item_id] = assessment.get("action", "")

    txns = await db.banktransaction.find_many(
        where={
            "tenant_id": tenant_id,
            "date": {"gte": run.period_start, "lte": run.period_end},
        },
        include={"account": True, "matched_invoice": True, "matched_bill": True},
        order={"date": "desc"},
    )

    rates_map: dict[str, float] = {}
    target_currency: str | None = None
    if display_currency:
        target_currency = display_currency.upper()
        if target_currency != "GBP":
            ex_rates = await db.exchangerate.find_many(where={"base_currency": "USD"})
            rates_map = {r.target_currency: float(r.rate) for r in ex_rates}
            rates_map.setdefault("USD", 1.0)

    def _convert(amount_minor: int, src: str) -> tuple[str, str]:
        major = amount_minor / 100
        if not target_currency or src.upper() == target_currency or src.upper() not in rates_map or target_currency not in rates_map:
            return f"{major:.2f}", src
        usd = major / rates_map[src.upper()]
        converted = usd * rates_map[target_currency]
        return f"{converted:.2f}", target_currency

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "date", "account_name", "description", "merchant_name",
        "amount", "currency", "bank_status", "ai_assessment",
        "matched_invoice_number", "matched_vendor", "reasoning",
    ])

    for t in txns:
        amount_str, currency_code = _convert(t.amount_minor, t.currency)
        writer.writerow([
            t.date.isoformat(),
            t.account.name if t.account else "",
            t.description or "",
            t.merchant_name or "",
            amount_str,
            currency_code,
            t.status,
            action_lookup_csv.get(t.id, ""),
            t.matched_invoice.invoice_number if t.matched_invoice else "",
            (t.matched_invoice.vendor if t.matched_invoice
             else (t.matched_bill.contact_name if t.matched_bill else "")),
            reasoning_lookup.get(t.id, ""),
        ])

    # Encode with utf-8-sig to prepend the UTF-8 BOM so Excel opens correctly
    csv_bytes = output.getvalue().encode('utf-8-sig')
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=\"reconciliation_{run_id}.csv\""},
    )


# ---------------------------------------------------------------------------
# POST /v1/reconcile — inline dataset reconciliation stub
# ---------------------------------------------------------------------------


class InlineReconcileRequest(BaseModel):
    source_dataset: list = []
    target_dataset: list = []


@router.post("/reconcile")
async def reconcile_datasets(_body: InlineReconcileRequest, _current_user: RequireOrgAuth) -> dict:
    """Inline dataset-to-dataset reconciliation stub. Full implementation via /v1/reconciliation/run."""
    return standard_response(data={
        "matched": [],
        "unmatched": [],
        "flagged": [],
        "confidence": 0.0,
        "status": "pending",
    })
