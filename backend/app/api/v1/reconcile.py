"""
Reconciliation API — /v1/reconciliation/*.
Endpoints: list runs, run items, trigger run, export CSV.
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


class ClosePeriodRequest(BaseModel):
    period_start: str
    period_end: str


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
# GET /v1/reconciliation/invoice-summary
# ---------------------------------------------------------------------------


@router.get("/reconciliation/invoice-summary")
async def get_invoice_summary(
    current_user: RequireOrgAuth,
    period_start: str = Query(...),
    period_end: str = Query(...),
    source: Optional[str] = Query(None),
    tool_id: Optional[str] = Query(None),
) -> dict:
    """Summarise accounting invoices for the given period."""
    db = get_db()
    tenant_id = current_user.tenant_id

    try:
        start_dt = datetime.fromisoformat(period_start)
        end_dt = datetime.fromisoformat(period_end)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid date format: {exc}") from exc

    where: dict = {
        "tenant_id": tenant_id,
        "issue_date": {"gte": start_dt, "lte": end_dt},
    }
    if source:
        where["source"] = source

    overdue_grace_days = 0
    if tool_id:
        tool_rec = await db.tool.find_first(where={"id": tool_id, "tenant_id": tenant_id})
        if tool_rec and isinstance(tool_rec.config_json, dict):
            overdue_grace_days = int(tool_rec.config_json.get("invoice_overdue_grace_days", 0))

    invoices = await db.accountinginvoice.find_many(where=where, order={"issue_date": "desc"})

    total_subtotal = sum(i.subtotal_cents or 0 for i in invoices)
    total_tax = sum(i.tax_cents or 0 for i in invoices)
    total_amount = sum(i.total_cents or 0 for i in invoices)
    total_outstanding = sum(i.outstanding_cents or 0 for i in invoices)
    paid_count = sum(1 for i in invoices if i.paid_at is not None)
    from datetime import timedelta
    overdue_cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=overdue_grace_days)
    overdue_count = sum(
        1 for i in invoices
        if i.paid_at is None and i.due_date is not None and i.due_date < overdue_cutoff
    )
    flagged = [
        {
            "id": i.id,
            "number": i.number,
            "contact_name": i.contact_name,
            "issue_date": i.issue_date.isoformat() if i.issue_date else None,
            "due_date": i.due_date.isoformat() if i.due_date else None,
            "subtotal_cents": i.subtotal_cents,
            "tax_cents": i.tax_cents,
            "total_cents": i.total_cents,
            "outstanding_cents": i.outstanding_cents,
            "status": i.status,
            "source": i.source,
            "flag_reason": "Missing tax — subtotal present but tax is zero",
        }
        for i in invoices
        if (i.subtotal_cents or 0) > 0 and (i.tax_cents or 0) == 0
    ]
    items = [
        {
            "id": i.id,
            "number": i.number,
            "contact_name": i.contact_name,
            "issue_date": i.issue_date.isoformat() if i.issue_date else None,
            "due_date": i.due_date.isoformat() if i.due_date else None,
            "subtotal_cents": i.subtotal_cents,
            "tax_cents": i.tax_cents,
            "total_cents": i.total_cents,
            "outstanding_cents": i.outstanding_cents,
            "paid_at": i.paid_at.isoformat() if i.paid_at else None,
            "status": i.status,
            "source": i.source,
            "currency": i.currency,
        }
        for i in invoices
    ]

    return standard_response(data={
        "period_start": period_start,
        "period_end": period_end,
        "total_invoices": len(invoices),
        "paid_count": paid_count,
        "overdue_count": overdue_count,
        "total_subtotal_cents": total_subtotal,
        "total_tax_cents": total_tax,
        "total_amount_cents": total_amount,
        "total_outstanding_cents": total_outstanding,
        "flagged": flagged,
        "items": items,
    })


# ---------------------------------------------------------------------------
# GET /v1/reconciliation/vat-summary
# ---------------------------------------------------------------------------


@router.get("/reconciliation/vat-summary")
async def get_vat_summary(
    current_user: RequireOrgAuth,
    period_start: str = Query(...),
    period_end: str = Query(...),
    source: Optional[str] = Query(None),
    tool_id: Optional[str] = Query(None),
) -> dict:
    """Summarise VAT position for the given period using accounting invoices."""
    db = get_db()
    tenant_id = current_user.tenant_id

    try:
        start_dt = datetime.fromisoformat(period_start)
        end_dt = datetime.fromisoformat(period_end)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid date format: {exc}") from exc

    expected_vat_rate = 20.0  # default UK standard rate
    if tool_id:
        tool_rec = await db.tool.find_first(where={"id": tool_id, "tenant_id": tenant_id})
        if tool_rec and isinstance(tool_rec.config_json, dict):
            expected_vat_rate = float(tool_rec.config_json.get("expected_vat_rate_pct", 20.0))

    inv_where: dict = {
        "tenant_id": tenant_id,
        "issue_date": {"gte": start_dt, "lte": end_dt},
    }
    if source:
        inv_where["source"] = source

    invoices = await db.accountinginvoice.find_many(where=inv_where, order={"issue_date": "desc"})

    output_vat = sum(i.tax_cents or 0 for i in invoices)
    net_sales = sum(i.subtotal_cents or 0 for i in invoices)
    vat_position = output_vat  # input VAT not available without bill tax_cents

    def _vat_flag_reason(inv) -> str | None:  # type: ignore[no-untyped-def]
        sub = inv.subtotal_cents or 0
        tax = inv.tax_cents or 0
        if sub > 0 and tax == 0:
            return "Missing VAT — sales invoice with no tax recorded"
        if sub > 0 and tax > 0:
            effective_rate = (tax / sub) * 100
            if abs(effective_rate - expected_vat_rate) > 1.0:
                return f"Unexpected VAT rate — effective {effective_rate:.1f}%, expected {expected_vat_rate:.0f}%"
        return None

    flagged = [
        {
            "id": i.id,
            "number": i.number,
            "contact_name": i.contact_name,
            "issue_date": i.issue_date.isoformat() if i.issue_date else None,
            "subtotal_cents": i.subtotal_cents,
            "tax_cents": i.tax_cents,
            "total_cents": i.total_cents,
            "source": i.source,
            "flag_reason": _vat_flag_reason(i),
        }
        for i in invoices
        if _vat_flag_reason(i) is not None
    ]

    invoice_lines = [
        {
            "id": i.id,
            "number": i.number,
            "contact_name": i.contact_name,
            "issue_date": i.issue_date.isoformat() if i.issue_date else None,
            "subtotal_cents": i.subtotal_cents,
            "tax_cents": i.tax_cents,
            "total_cents": i.total_cents,
            "status": i.status,
            "source": i.source,
            "currency": i.currency,
        }
        for i in invoices
    ]

    return standard_response(data={
        "period_start": period_start,
        "period_end": period_end,
        "output_vat_cents": output_vat,
        "net_sales_cents": net_sales,
        "vat_position_cents": vat_position,
        "total_invoices": len(invoices),
        "flagged_count": len(flagged),
        "flagged": flagged,
        "invoice_lines": invoice_lines,
    })


# ---------------------------------------------------------------------------
# POST /v1/reconciliation/close-period
# ---------------------------------------------------------------------------


@router.post("/reconciliation/close-period")
async def close_period(
    body: ClosePeriodRequest,
    current_user: RequireOrgAuth,
) -> dict:
    """Mark a period as closed. Writes an immutable audit log entry."""
    db = get_db()
    tenant_id = current_user.tenant_id

    try:
        datetime.fromisoformat(body.period_start)
        datetime.fromisoformat(body.period_end)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid date format: {exc}") from exc

    closed_at = datetime.now(UTC)

    await db.auditlog.create(data={
        "tenant_id": tenant_id,
        "actor": current_user.email or "unknown",
        "action": "period_closed",
        "reasoning_trace_json": {
            "period_start": body.period_start,
            "period_end": body.period_end,
            "closed_by": current_user.email,
            "closed_at": closed_at.isoformat(),
        },
        "model_version": "manual",
    })

    return standard_response(data={
        "closed_at": closed_at.isoformat(),
        "closed_by": current_user.email,
        "period_start": body.period_start,
        "period_end": body.period_end,
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
