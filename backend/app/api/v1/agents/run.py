import base64
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Path
from pydantic import BaseModel

from app.core.db import get_db
from app.core.dispatch import enqueue_for_tool_type
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.queue.pool import get_queue_pool

_logger = get_logger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


class RunRequest(BaseModel):
    file_bytes_b64: str
    content_type: str


@router.post("/{tool_id}/run")
async def run_agent(
    current_user: RequireOrgAuth,
    tool_id: str = Path(...),
    body: RunRequest = ...,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    """
    Idempotent execution endpoint. Enqueues the invoice processing tool via arq.
    Same Idempotency-Key + tenant + tool returns the existing execution record.
    Tenant isolation enforced at application layer; RLS enforced at DB layer (Phase 2).
    """
    db = get_db()
    tenant_id = current_user.tenant_id

    # Validate tool belongs to tenant
    tool = await db.tool.find_first(
        where={"id": tool_id, "tenant_id": tenant_id}
    )
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    if tool.status == "inactive":
        raise HTTPException(status_code=409, detail="Tool is inactive")

    # Idempotency: check for existing execution with this key (stored in input_ref)
    existing = await db.execution.find_first(
        where={
            "tenant_id": tenant_id,
            "tool_id": tool_id,
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

    # Extract policy config from tool's config_json
    policy_config = {}
    if tool.config_json and isinstance(tool.config_json, dict):
        policy_config = tool.config_json.get("policy", {})

    # Create execution record (status: queued)
    execution = await db.execution.create(
        data={
            "tenant_id": tenant_id,
            "tool_id": tool_id,
            "input_ref": idempotency_key,
            "decision": "pending",
            "confidence": 0.0,
            "status": "queued",
            **({"triggered_by_email": current_user.email} if current_user.email else {}),
        }
    )

    # Enqueue the job
    pool = await get_queue_pool()
    await pool.enqueue_job(
        "run_invoice_job",
        execution_id=execution.id,
        tenant_id=tenant_id,
        tool_id=tool_id,
        file_bytes=file_bytes,
        content_type=body.content_type,
        policy_config=policy_config,
    )

    _logger.info(
        "execution_queued",
        extra={"execution_id": execution.id, "tool_id": tool_id, "tenant_id": tenant_id},
    )

    return standard_response(
        data={
            "execution_id": execution.id,
            "status": "queued",
            "decision": "pending",
            "idempotent": False,
        }
    )


@router.post("/{tool_id}/executions/{execution_id}/cancel")
async def cancel_execution(
    current_user: RequireOrgAuth,
    tool_id: str = Path(...),
    execution_id: str = Path(...),
):
    """Mark a queued or running execution as cancelled."""
    db = get_db()
    tenant_id = current_user.tenant_id

    execution = await db.execution.find_first(
        where={"id": execution_id, "tenant_id": tenant_id, "tool_id": tool_id}
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    if execution.status not in ("queued", "running"):
        raise HTTPException(status_code=409, detail=f"Execution is already {execution.status}")

    await db.execution.update(
        where={"id": execution_id},
        data={"status": "cancelled", "decision": "cancelled"},
    )

    return standard_response(data={"execution_id": execution_id, "status": "cancelled"})


class TriggerRequest(BaseModel):
    payload: dict[str, Any] = {}


@router.post("/{tool_id}/trigger")
async def trigger_agent(
    current_user: RequireOrgAuth,
    tool_id: str = Path(...),
    body: TriggerRequest = ...,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    """
    Dashboard execution path. Clerk-authenticated, generic JSON payload.
    Enqueues the named tool directly via arq.
    Same Idempotency-Key + tenant + tool returns the existing execution record.
    """
    db = get_db()
    tenant_id = current_user.tenant_id

    # --- Find tool by id and tenant ---
    tool = await db.tool.find_first(
        where={"id": tool_id, "tenant_id": tenant_id}
    )
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    if tool.status == "inactive":
        raise HTTPException(status_code=409, detail="Tool is inactive")

    # --- Idempotency check ---
    existing = await db.execution.find_first(
        where={
            "tenant_id": tenant_id,
            "tool_id": tool_id,
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

    # --- Extract policy config from tool config ---
    policy_config: dict[str, Any] = (
        tool.config_json if tool.config_json and isinstance(tool.config_json, dict) else {}
    )

    _logger.info(
        "trigger_received",
        extra={
            "tool_id": tool_id,
            "tool_type": tool.type,
            "tenant_id": tenant_id,
            "payload_keys": list(body.payload.keys()),
            "transaction_count": len(body.payload.get("transaction_ids", [])),
        },
    )

    # --- Create execution record ---
    execution = await db.execution.create(
        data={
            "tenant_id": tenant_id,
            "tool_id": tool_id,
            "input_ref": idempotency_key,
            "decision": "pending",
            "confidence": 0.0,
            "status": "queued",
            **({"triggered_by_email": current_user.email} if current_user.email else {}),
        }
    )

    # --- Enqueue job directly ---
    pool = await get_queue_pool()
    await enqueue_for_tool_type(
        pool=pool,
        tool_type=tool.type,
        execution_id=execution.id,
        tenant_id=tenant_id,
        tool_id=tool_id,
        payload={**body.payload, **policy_config},
    )

    _logger.info(
        "trigger_queued",
        extra={
            "execution_id": execution.id,
            "tool_id": tool_id,
            "tool_type": tool.type,
            "tenant_id": tenant_id,
            "source": "dashboard",
        },
    )

    return standard_response(
        data={
            "execution_id": execution.id,
            "status": "queued",
            "decision": "pending",
            "idempotent": False,
        }
    )
