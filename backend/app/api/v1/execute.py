import hashlib
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.core.db import get_db
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.queue.pool import get_queue_pool

_logger = get_logger(__name__)

router = APIRouter(prefix="/execute", tags=["agents"])

TOOL_TYPE_TO_EVENT: dict[str, str] = {
    # Pre-consolidation names — kept for backwards compatibility
    "invoice_processing":    "invoice_received",
    "receipt_processing":    "receipt_received",
    "expense_control":       "expense_control_run",
    "collections":           "collection_triggered",
    "fraud_detection":       "fraud_check_requested",
    "treasury":              "treasury_run",
    "compliance":            "compliance_check_requested",
    "compliance_check":      "compliance_check_requested",
    # Current names
    "reconciliation":        "reconciliation_run",
    "revenue_recognition":   "revenue_recognition_run",
    "ai_accountant":         "transaction_posted",
    "credit_underwriting":   "credit_assessment_run",
    "document_intelligence": "document_received",
    "spend_control":         "spend_control_run",
    "ar_collections":        "ar_collections_run",
    "risk_compliance":       "risk_compliance_run",
    "treasury_cash":         "treasury_cash_run",
    "tax_compliance":        "tax_compliance_run",
    "financial_reporting":   "financial_report_run",
    "payment_run":           "payment_run_requested",
    "budgeting":             "budget_check_run",
}


class ExecuteRequest(BaseModel):
    tool: str
    payload: dict[str, Any] = {}


@router.post("")
async def execute(
    body: ExecuteRequest,
    authorization: str = Header(..., alias="Authorization"),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    """
    Direct API execution path for external callers.
    Authenticates via API key (Bearer ck_live_...), enqueues the requested tool.
    Same Idempotency-Key + tenant + tool returns the existing execution record.
    """
    # --- Auth: extract and validate API key format ---
    if not authorization.startswith("Bearer ck_live_"):
        raise HTTPException(status_code=401, detail="Invalid API key format")

    raw_key = authorization.removeprefix("Bearer ")
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    db = get_db()

    # --- Look up API key record ---
    api_key = await db.apikey.find_first(
        where={"key_hash": key_hash, "status": "active"}
    )
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")

    # --- Check expiry ---
    if api_key.expires_at is not None:
        expires_at = api_key.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(tz=timezone.utc) > expires_at:
            raise HTTPException(status_code=401, detail="API key has expired")

    tenant_id: str = api_key.tenant_id

    # --- Validate tool type ---
    if body.tool not in TOOL_TYPE_TO_EVENT:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown tool type '{body.tool}'. Valid types: {list(TOOL_TYPE_TO_EVENT)}",
        )

    event_type = TOOL_TYPE_TO_EVENT[body.tool]

    # --- Find active tool for this tenant ---
    tool = await db.tool.find_first(
        where={"tenant_id": tenant_id, "type": body.tool, "status": "active"}
    )
    if not tool:
        raise HTTPException(
            status_code=404,
            detail=f"No active tool of type '{body.tool}' found for this tenant",
        )

    # --- Idempotency check ---
    existing = await db.execution.find_first(
        where={
            "tenant_id": tenant_id,
            "tool_id": tool.id,
            "input_ref": idempotency_key,
        }
    )
    if existing and existing.status != "failed":
        return standard_response(
            data={
                "execution_id": existing.id,
                "status": existing.status,
                "decision": existing.decision,
                "idempotent": True,
            }
        )

    # --- Create execution record ---
    execution = await db.execution.create(
        data={
            "tenant_id": tenant_id,
            "tool_id": tool.id,
            "input_ref": idempotency_key,
            "decision": "pending",
            "confidence": 0.0,
            "status": "queued",
        }
    )

    # --- Enqueue job ---
    pool = await get_queue_pool()
    await pool.enqueue_job(
        "run_orchestrator_job",
        execution_id=execution.id,
        tenant_id=tenant_id,
        tool_id=tool.id,
        event_type=event_type,
        payload=body.payload,
    )

    _logger.info(
        "execution_queued",
        extra={
            "execution_id": execution.id,
            "tool_id": tool.id,
            "tenant_id": tenant_id,
            "source": "api_key",
        },
    )

    # --- Fire-and-forget: update last_used_at (non-critical) ---
    try:
        await db.apikey.update(
            where={"id": api_key.id},
            data={"last_used_at": datetime.now(tz=timezone.utc)},
        )
    except Exception:
        _logger.warning(
            "api_key_last_used_update_failed",
            extra={"api_key_id": api_key.id},
        )

    return standard_response(
        data={
            "execution_id": execution.id,
            "status": "queued",
            "decision": "pending",
            "idempotent": False,
        }
    )


def _auth_api_key(authorization: str):
    """Extract and return (raw_key, key_hash) or raise 401."""
    if not authorization.startswith("Bearer ck_live_"):
        raise HTTPException(status_code=401, detail="Invalid API key format")
    raw_key = authorization.removeprefix("Bearer ")
    return hashlib.sha256(raw_key.encode()).hexdigest()


@router.get("/{execution_id}")
async def get_execution(
    execution_id: str,
    authorization: str = Header(..., alias="Authorization"),
):
    """
    Poll for execution result.
    Authenticated via API key (same as POST /execute).
    Returns status, decision, confidence, reasoning trace, and timing.
    """
    key_hash = _auth_api_key(authorization)
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

    execution = await db.execution.find_first(
        where={"id": execution_id, "tenant_id": tenant_id},
        include={"tool": True},
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    # Fetch reasoning from the most recent audit log for this execution
    audit = await db.auditlog.find_first(
        where={"execution_id": execution_id, "tenant_id": tenant_id},
        order={"created_at": "desc"},
    )

    return standard_response(
        data={
            "execution_id": execution.id,
            "tool": execution.tool.type if execution.tool else None,
            "status": execution.status,
            "decision": execution.decision,
            "confidence": execution.confidence,
            "duration_ms": execution.duration_ms,
            "error": execution.error_message,
            "reasoning_trace": audit.reasoning_trace_json if audit else None,
            "created_at": execution.created_at.isoformat(),
        }
    )
