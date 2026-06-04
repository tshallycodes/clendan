import base64

from fastapi import APIRouter, Header, HTTPException, Path
from pydantic import BaseModel

from app.core.db import get_db
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.queue.pool import get_queue_pool

_logger = get_logger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


class RunRequest(BaseModel):
    file_bytes_b64: str
    content_type: str


@router.post("/{worker_id}/run")
async def run_agent(
    worker_id: str = Path(...),
    body: RunRequest = ...,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    """
    Idempotent execution endpoint. Enqueues the invoice processing worker via arq.
    Same Idempotency-Key + tenant + worker returns the existing execution record.
    Tenant isolation enforced at application layer; RLS enforced at DB layer (Phase 2).
    """
    db = get_db()

    # Validate worker belongs to tenant
    worker = await db.worker.find_first(
        where={"id": worker_id, "tenant_id": x_tenant_id}
    )
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    if worker.status == "inactive":
        raise HTTPException(status_code=409, detail="Worker is inactive")

    # Idempotency: check for existing execution with this key (stored in input_ref)
    existing = await db.execution.find_first(
        where={
            "tenant_id": x_tenant_id,
            "worker_id": worker_id,
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

    # Validate content type
    allowed = {"application/pdf", "image/png", "image/jpeg"}
    if body.content_type not in allowed:
        raise HTTPException(status_code=415, detail=f"Unsupported content_type '{body.content_type}'")

    try:
        file_bytes = base64.b64decode(body.file_bytes_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="file_bytes_b64 is not valid base64")

    if not file_bytes:
        raise HTTPException(status_code=400, detail="file_bytes_b64 decoded to empty bytes")

    # Extract policy config from worker's config_json
    policy_config = {}
    if worker.config_json and isinstance(worker.config_json, dict):
        policy_config = worker.config_json.get("policy", {})

    # Create execution record (status: queued)
    execution = await db.execution.create(
        data={
            "tenant_id": x_tenant_id,
            "worker_id": worker_id,
            "input_ref": idempotency_key,
            "decision": "pending",
            "confidence": 0.0,
            "status": "queued",
        }
    )

    # Enqueue the job
    pool = await get_queue_pool()
    await pool.enqueue_job(
        "run_invoice_job",
        execution_id=execution.id,
        tenant_id=x_tenant_id,
        worker_id=worker_id,
        file_bytes=file_bytes,
        content_type=body.content_type,
        policy_config=policy_config,
    )

    _logger.info(
        "execution_queued",
        extra={"execution_id": execution.id, "worker_id": worker_id, "tenant_id": x_tenant_id},
    )

    return standard_response(
        data={
            "execution_id": execution.id,
            "status": "queued",
            "decision": "pending",
            "idempotent": False,
        }
    )
