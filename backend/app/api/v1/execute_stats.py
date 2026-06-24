"""GET /execute/stats — execution aggregate stats per tool, authenticated via API key."""
import hashlib
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Header, HTTPException

from app.core.db import get_db
from app.core.logging import get_logger
from app.core.responses import standard_response

_logger = get_logger(__name__)

router = APIRouter(prefix="/execute", tags=["agents"])

_TOOL_TYPES = [
    "reconciliation",
    "document_intelligence",
    "ai_accountant",
    "spend_control",
    "ar_collections",
    "risk_compliance",
    "treasury_cash",
    "revenue_recognition",
    "credit_underwriting",
    "tax_compliance",
    "financial_reporting",
    "payment_run",
    "budgeting",
]


@router.get("/stats")
async def execution_stats(
    authorization: str = Header(..., alias="Authorization"),
):
    """
    Returns aggregate execution counts per tool type for the authenticated tenant.
    Authenticated via API key (same as POST /execute).
    """
    if not authorization.startswith("ck_live_"):
        raise HTTPException(status_code=401, detail="Invalid API key format")

    key_hash = hashlib.sha256(authorization.encode()).hexdigest()

    db = get_db()

    api_key = await db.apikey.find_first(
        where={"key_hash": key_hash, "status": "active"}
    )
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")

    if api_key.expires_at is not None:
        expires_at = api_key.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(tz=timezone.utc) > expires_at:
            raise HTTPException(status_code=401, detail="API key has expired")

    tenant_id: str = api_key.tenant_id

    # Fetch all executions for this tenant with tool relation
    executions = await db.execution.find_many(
        where={"tenant_id": tenant_id},
        include={"tool": True},
    )

    cutoff_30d = datetime.now(tz=timezone.utc) - timedelta(days=30)

    by_tool: dict[str, dict[str, int]] = {
        wt: {"total": 0, "auto_approved": 0, "pending": 0, "blocked": 0}
        for wt in _TOOL_TYPES
    }

    total_executions = 0
    last_30_days = 0

    for ex in executions:
        tool_type = (ex.tool.type if ex.tool else None) or "unknown"
        if tool_type not in by_tool:
            by_tool[tool_type] = {"total": 0, "auto_approved": 0, "pending": 0, "blocked": 0}

        by_tool[tool_type]["total"] += 1
        total_executions += 1

        created = ex.created_at
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created and created >= cutoff_30d:
            last_30_days += 1

        decision = (ex.decision or "").lower()
        ex_status = (ex.status or "").lower()

        if decision in ("approved", "auto_approved") or (
            ex_status == "completed" and decision not in ("blocked", "approval_required", "pending", "failed")
        ):
            by_tool[tool_type]["auto_approved"] += 1
        elif decision == "blocked" or ex_status == "failed":
            by_tool[tool_type]["blocked"] += 1
        elif decision in ("approval_required", "pending") or ex_status in ("pending", "queued"):
            by_tool[tool_type]["pending"] += 1

    return standard_response(
        data={
            "by_tool": by_tool,
            "total_executions": total_executions,
            "last_30_days": last_30_days,
        }
    )
