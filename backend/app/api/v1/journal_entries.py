"""
Journal Entries API — /v1/journal-entries
Endpoints: list, create, get, post, void.
All queries scoped to current_user.tenant_id — no cross-tenant access.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app.core.db import get_db
from app.core.logging import get_logger, get_trace_id
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.tools.journal_entries import JournalEntryTool

logger = get_logger(__name__)

router = APIRouter(tags=["journal-entries"])

VALID_ENTRY_TYPES = {"payroll", "adjustment", "accrual", "prepayment", "depreciation", "manual"}


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class JournalEntryLineIn(BaseModel):
    account_code: str
    account_name: str
    debit_minor: int = 0
    credit_minor: int = 0
    description: Optional[str] = None

    @field_validator("debit_minor", "credit_minor")
    @classmethod
    def non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Line amounts must be non-negative integers")
        return v


class CreateJournalEntryRequest(BaseModel):
    period: str                          # "YYYY-MM"
    description: str
    lines: list[JournalEntryLineIn]
    entry_type: str = "adjustment"
    auto_approve_threshold_minor: Optional[int] = 5_000_000

    @field_validator("lines")
    @classmethod
    def lines_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("lines cannot be empty")
        return v

    @field_validator("entry_type")
    @classmethod
    def valid_entry_type(cls, v: str) -> str:
        if v not in VALID_ENTRY_TYPES:
            raise ValueError(f"entry_type must be one of: {', '.join(sorted(VALID_ENTRY_TYPES))}")
        return v


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_entry(entry, lines) -> dict:
    return {
        "id": entry.id,
        "tenant_id": entry.tenant_id,
        "period": entry.period,
        "entry_type": entry.entry_type,
        "description": entry.description,
        "status": entry.status,
        "total_minor": entry.total_minor,
        "currency": entry.currency,
        "posted_at": entry.posted_at.isoformat() if entry.posted_at else None,
        "created_at": entry.created_at.isoformat(),
        "lines": [
            {
                "id": ln.id,
                "account_code": ln.account_code,
                "account_name": ln.account_name,
                "debit_minor": ln.debit_minor,
                "credit_minor": ln.credit_minor,
                "description": ln.description,
            }
            for ln in lines
        ],
    }


# ---------------------------------------------------------------------------
# GET /v1/journal-entries
# ---------------------------------------------------------------------------


@router.get("/journal-entries")
async def list_journal_entries(
    current_user: RequireOrgAuth,
    period: Optional[str] = None,
    limit: int = 20,
    skip: int = 0,
) -> dict:
    """List journal entries for the tenant, newest first. Optional ?period=YYYY-MM, ?limit, ?skip."""
    db = get_db()
    tenant_id = current_user.tenant_id

    where: dict = {"tenant_id": tenant_id}
    if period:
        where["period"] = period

    total, entries = await db.journalentry.count(where=where), await db.journalentry.find_many(
        where=where,
        order={"created_at": "desc"},
        take=limit,
        skip=skip,
        include={"lines": True},
    )

    return standard_response(data={
        "entries": [_format_entry(e, e.lines or []) for e in entries],
        "total": total,
        "has_more": skip + len(entries) < total,
    })


# ---------------------------------------------------------------------------
# POST /v1/journal-entries
# ---------------------------------------------------------------------------


@router.post("/journal-entries")
async def create_journal_entry(
    body: CreateJournalEntryRequest,
    current_user: RequireOrgAuth,
) -> dict:
    """
    Create a journal entry.
    Returns 422 if debit/credit lines do not balance.
    Entries over auto_approve_threshold_minor are created with status pending_approval.
    """
    tenant_id = current_user.tenant_id
    db = get_db()

    # Resolve the tool_id for this tenant's journal entry tool (or use a sentinel)
    tool = await db.tool.find_first(
        where={"tenant_id": tenant_id, "type": "journal_entries"}
    )
    tool_id = tool.id if tool else f"manual:{tenant_id}"

    # Use the authenticated user's preferred currency
    user = await db.user.find_first(where={"clerk_user_id": current_user.user_id})
    currency = user.preferred_currency if user and user.preferred_currency else "USD"

    tool_instance = JournalEntryTool()
    try:
        result = await tool_instance.create_payroll_entry(
            period=body.period,
            tenant_id=tenant_id,
            tool_id=tool_id,
            lines=[ln.model_dump() for ln in body.lines],
            description=body.description,
            auto_approve_threshold_minor=body.auto_approve_threshold_minor or 5_000_000,
            entry_type=body.entry_type,
            currency=currency,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Fetch the created entry with lines to return full shape
    entry = await db.journalentry.find_unique(
        where={"id": result.entry_id},
        include={"lines": True},
    )
    if entry is None:
        raise HTTPException(status_code=500, detail="Entry created but could not be fetched")

    return standard_response(data={"entry": _format_entry(entry, entry.lines or [])})


# ---------------------------------------------------------------------------
# GET /v1/journal-entries/{entry_id}
# ---------------------------------------------------------------------------


@router.get("/journal-entries/{entry_id}")
async def get_journal_entry(
    entry_id: str,
    current_user: RequireOrgAuth,
) -> dict:
    """Fetch a single journal entry with its lines."""
    db = get_db()
    entry = await db.journalentry.find_first(
        where={"id": entry_id, "tenant_id": current_user.tenant_id},
        include={"lines": True},
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    return standard_response(data={"entry": _format_entry(entry, entry.lines or [])})


# ---------------------------------------------------------------------------
# POST /v1/journal-entries/{entry_id}/post
# ---------------------------------------------------------------------------


@router.post("/journal-entries/{entry_id}/post")
async def post_journal_entry(
    entry_id: str,
    current_user: RequireOrgAuth,
) -> dict:
    """
    Post an approved journal entry (status: approved → posted).
    Returns 404 if not found, 409 if not in approved status.
    """
    tenant_id = current_user.tenant_id

    tool_instance = JournalEntryTool()
    try:
        result = await tool_instance.post_entry(entry_id=entry_id, tenant_id=tenant_id)
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg) from exc
        raise HTTPException(status_code=409, detail=msg) from exc

    return standard_response(data=result)


# ---------------------------------------------------------------------------
# DELETE /v1/journal-entries/{entry_id}
# ---------------------------------------------------------------------------


@router.delete("/journal-entries/{entry_id}")
async def void_journal_entry(
    entry_id: str,
    current_user: RequireOrgAuth,
) -> dict:
    """
    Soft-delete a draft journal entry by setting status to 'voided'.
    Only entries with status='draft' can be voided.
    Returns 404 if not found, 409 if not in draft status.
    """
    db = get_db()
    tenant_id = current_user.tenant_id
    trace_id = get_trace_id()

    entry = await db.journalentry.find_first(
        where={"id": entry_id, "tenant_id": tenant_id}
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="Journal entry not found")

    if entry.status != "draft":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot void entry with status '{entry.status}' — only draft entries can be voided",
        )

    updated = await db.journalentry.update(
        where={"id": entry_id},
        data={"status": "voided"},
    )

    # Audit — must succeed before returning
    await db.auditlog.create(
        data={
            "tenant_id": tenant_id,
            "actor": f"user:{current_user.user_id}",
            "action": "journal_entry:void",
            "reasoning_trace_json": {
                "trace_id": trace_id,
                "entry_id": entry_id,
                "period": entry.period,
                "entry_type": entry.entry_type,
                "total_minor": entry.total_minor,
                "previous_status": entry.status,
            },
            "model_version": "journal_entries_v1",
        }
    )

    logger.info(
        "journal_entry_voided",
        extra={"tenant_id": tenant_id, "entry_id": entry_id},
    )

    return standard_response(data={"entry_id": updated.id, "status": updated.status})


# ---------------------------------------------------------------------------
# GET /v1/journal-entries/suggest/payroll-run/{run_id}
# ---------------------------------------------------------------------------


@router.get("/journal-entries/suggest/payroll-run/{run_id}")
async def suggest_payroll_journal_entry(
    run_id: str,
    current_user: RequireOrgAuth,
) -> dict:
    """Return a pre-filled journal entry suggestion from a completed payroll run."""
    db = get_db()
    tenant_id = current_user.tenant_id

    run = await db.payrollrun.find_first(
        where={"id": run_id, "tenant_id": tenant_id}
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Payroll run not found")

    roster: list[dict] = run.roster_json or []
    lines: list[dict] = []
    for employee in roster:
        name: str = employee.get("name", "Unknown")
        expected_minor: int = employee.get("expected_minor", 0)
        lines.append({
            "account_code": "5000",
            "account_name": f"Salary Expense — {name}",
            "debit_minor": expected_minor,
            "credit_minor": 0,
        })

    lines.append({
        "account_code": "2100",
        "account_name": "Wages Payable",
        "debit_minor": 0,
        "credit_minor": run.total_payroll_minor,
    })

    return standard_response(data={
        "suggestion": {
            "period": run.period,
            "description": f"Payroll — {run.period}",
            "entry_type": "payroll",
            "lines": lines,
        }
    })


# ---------------------------------------------------------------------------
# GET /v1/journal-entries/suggest/reconciliation-run/{run_id}
# ---------------------------------------------------------------------------


@router.get("/journal-entries/suggest/reconciliation-run/{run_id}")
async def suggest_reconciliation_journal_entry(
    run_id: str,
    current_user: RequireOrgAuth,
) -> dict:
    """Return a pre-filled journal entry suggestion from a completed reconciliation run."""
    db = get_db()
    tenant_id = current_user.tenant_id

    run = await db.reconciliationrun.find_first(
        where={"id": run_id, "tenant_id": tenant_id}
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Reconciliation run not found")

    txns = await db.banktransaction.find_many(
        where={
            "tenant_id": tenant_id,
            "date": {"gte": run.period_start, "lte": run.period_end},
            "status": {"in": ["flagged", "unmatched"]},
        },
        include={"account": True},
    )

    period_str: str = run.period_start.strftime("%Y-%m")

    if not txns:
        lines: list[dict] = [
            {
                "account_code": "3000",
                "account_name": "Reconciliation Adjustment — No Items",
                "debit_minor": 0,
                "credit_minor": 0,
            },
            {
                "account_code": "3999",
                "account_name": "Reconciliation Clearing Account",
                "debit_minor": 0,
                "credit_minor": 0,
            },
        ]
    else:
        groups: dict[str, int] = {}
        for t in txns:
            group_name = t.account.name if t.account else "Unknown Account"
            groups[group_name] = groups.get(group_name, 0) + t.amount_minor

        lines = []
        for group_name, group_total in groups.items():
            lines.append({
                "account_code": "3000",
                "account_name": f"Reconciliation Adjustment — {group_name}",
                "debit_minor": group_total,
                "credit_minor": 0,
            })

        lines.append({
            "account_code": "3999",
            "account_name": "Reconciliation Clearing Account",
            "debit_minor": 0,
            "credit_minor": sum(groups.values()),
        })

    return standard_response(data={
        "suggestion": {
            "period": period_str,
            "description": f"Reconciliation Adjustment — {period_str}",
            "entry_type": "adjustment",
            "lines": lines,
        }
    })


# ---------------------------------------------------------------------------
# GET /v1/journal-entries/suggest/categorisation
# ---------------------------------------------------------------------------


@router.get("/journal-entries/suggest/categorisation")
async def suggest_categorisation_journal_entry(
    current_user: RequireOrgAuth,
) -> dict:
    """Return a pre-filled journal entry suggestion from categorised/matched transactions."""
    db = get_db()
    tenant_id = current_user.tenant_id

    txns = await db.banktransaction.find_many(
        where={
            "tenant_id": tenant_id,
            "status": {"in": ["categorised", "matched"]},
            "ai_category": {"not": None},
        }
    )

    current_period: str = datetime.now(UTC).strftime("%Y-%m")

    groups: dict[str, int] = {}
    for t in txns:
        category: str = t.ai_category or "uncategorised"
        groups[category] = groups.get(category, 0) + t.amount_minor

    lines: list[dict] = []
    for category, group_total in groups.items():
        lines.append({
            "account_code": "4000",
            "account_name": category.replace("_", " ").title(),
            "debit_minor": group_total,
            "credit_minor": 0,
        })

    lines.append({
        "account_code": "1000",
        "account_name": "Bank Account",
        "debit_minor": 0,
        "credit_minor": sum(groups.values()),
    })

    return standard_response(data={
        "suggestion": {
            "period": current_period,
            "description": f"Transaction Accruals — {current_period}",
            "entry_type": "accrual",
            "lines": lines,
        }
    })
