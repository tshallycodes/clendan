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

WORKER_TYPE_TO_EVENT: dict[str, str] = {
    "invoice_processing":  "invoice_received",
    "fraud_detection":     "fraud_check_requested",
    "collections":         "collection_triggered",
    "expense_control":     "expense_submitted",
    "reconciliation":      "reconciliation_requested",
    "revenue_recognition": "revenue_recognition_run",
    "compliance_check":    "compliance_check_requested",
}


class ExecuteRequest(BaseModel):
    worker: str
    payload: dict[str, Any] = {}


@router.post("")
async def execute(
    body: ExecuteRequest,
    authorization: str = Header(..., alias="Authorization"),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    """
    Direct API execution path for external callers.
    Authenticates via API key (Bearer ck_live_...), enqueues the requested worker.
    Same Idempotency-Key + tenant + worker returns the existing execution record.
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

    # --- Validate worker type ---
    if body.worker not in WORKER_TYPE_TO_EVENT:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown worker type '{body.worker}'. Valid types: {list(WORKER_TYPE_TO_EVENT)}",
        )

    event_type = WORKER_TYPE_TO_EVENT[body.worker]

    # --- Find active worker for this tenant ---
    worker = await db.worker.find_first(
        where={"tenant_id": tenant_id, "type": body.worker, "status": "active"}
    )
    if not worker:
        raise HTTPException(
            status_code=404,
            detail=f"No active worker of type '{body.worker}' found for this tenant",
        )

    # --- Idempotency check ---
    existing = await db.execution.find_first(
        where={
            "tenant_id": tenant_id,
            "worker_id": worker.id,
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
            "worker_id": worker.id,
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
        worker_id=worker.id,
        event_type=event_type,
        payload=body.payload,
    )

    _logger.info(
        "execution_queued",
        extra={
            "execution_id": execution.id,
            "worker_id": worker.id,
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
