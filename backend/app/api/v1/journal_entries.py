"""
Journal Entries API — /v1/journal-entries
Endpoints: list, create, get, post, void.
All queries scoped to current_user.tenant_id — no cross-tenant access.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app.core.db import get_db
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.tools.journal_entries import JournalEntryTool

logger = get_logger(__name__)

router = APIRouter(tags=["journal-entries"])


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
    auto_approve_threshold_minor: Optional[int] = 5_000_000

    @field_validator("lines")
    @classmethod
    def lines_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("lines cannot be empty")
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
    limit: int = 50,
) -> dict:
    """List journal entries for the tenant, newest first. Optional ?period=YYYY-MM filter."""
    db = get_db()
    tenant_id = current_user.tenant_id

    where: dict = {"tenant_id": tenant_id}
    if period:
        where["period"] = period

    entries = await db.journalentry.find_many(
        where=where,
        order={"created_at": "desc"},
        take=limit,
        include={"lines": True},
    )

    return standard_response(data={
        "entries": [_format_entry(e, e.lines or []) for e in entries],
        "total": len(entries),
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
    Create a payroll journal entry.
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

    tool_instance = JournalEntryTool()
    try:
        result = await tool_instance.create_payroll_entry(
            period=body.period,
            tenant_id=tenant_id,
            tool_id=tool_id,
            lines=[ln.model_dump() for ln in body.lines],
            description=body.description,
            auto_approve_threshold_minor=body.auto_approve_threshold_minor or 5_000_000,
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

    logger.info(
        "journal_entry_voided",
        extra={"tenant_id": tenant_id, "entry_id": entry_id},
    )

    return standard_response(data={"entry_id": updated.id, "status": updated.status})
