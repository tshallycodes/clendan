import asyncio
import hashlib
from datetime import datetime, timezone, UTC
from typing import Any

from fastapi import APIRouter, File, Header, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app.core.db import get_db
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.queue.pool import get_queue_pool
from app.tools.document_intelligence import (
    _ALLOWED_CONTENT_TYPES,
    _MAX_FILE_BYTES,
    _generate_thumbnail,
)

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


async def _resolve_api_key(authorization: str) -> tuple[str, str]:
    """Validate API key and return (tenant_id, api_key_id), or raise 401."""
    if not authorization.startswith("ck_live_"):
        raise HTTPException(status_code=401, detail="Invalid API key format")
    key_hash = hashlib.sha256(authorization.encode()).hexdigest()
    db = get_db()
    api_key = await db.apikey.find_first(where={"key_hash": key_hash, "status": "active"})
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")
    if api_key.expires_at is not None:
        expires_at = api_key.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(tz=timezone.utc) > expires_at:
            raise HTTPException(status_code=401, detail="API key has expired")
    return api_key.tenant_id, api_key.id


@router.post("")
async def execute(
    body: ExecuteRequest,
    authorization: str = Header(..., alias="Authorization"),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    """
    Direct API execution path for external callers.
    Authenticates via API key (ck_live_...), enqueues the requested tool.
    Same Idempotency-Key + tenant + tool returns the existing execution record.
    """
    tenant_id, api_key_id = await _resolve_api_key(authorization)
    db = get_db()

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
            where={"id": api_key_id},
            data={"last_used_at": datetime.now(tz=timezone.utc)},
        )
    except Exception:
        _logger.warning(
            "api_key_last_used_update_failed",
            extra={"api_key_id": api_key_id},
        )

    return standard_response(
        data={
            "execution_id": execution.id,
            "status": "queued",
            "decision": "pending",
            "idempotent": False,
        }
    )


@router.post("/document-intelligence")
async def execute_document_intelligence(
    file: UploadFile = File(...),
    authorization: str = Header(..., alias="Authorization"),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    """
    Upload a file for analysis via API key. Accepts PDF, Word, PNG, JPG, WebP.
    Returns execution_id to poll via GET /execute/{execution_id}.
    The completed response includes extracted_json with summary, risks, parties, key dates.
    """
    tenant_id, _ = await _resolve_api_key(authorization)
    db = get_db()

    content_type = file.content_type or "application/pdf"
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Allowed: PDF, Word (.docx), PNG, JPG, WebP",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(file_bytes) > _MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")

    tool = await db.tool.find_first(
        where={"tenant_id": tenant_id, "type": "document_intelligence", "status": "active"}
    )
    if not tool:
        raise HTTPException(
            status_code=404,
            detail="No active document_intelligence tool found for this tenant",
        )

    # Idempotency: return existing execution if this key was already submitted
    existing = await db.execution.find_first(
        where={"tenant_id": tenant_id, "tool_id": tool.id, "input_ref": idempotency_key}
    )
    if existing and existing.status != "failed":
        doc = await db.document.find_first(where={"execution_id": existing.id, "tenant_id": tenant_id})
        return standard_response(data={
            "document_id": doc.id if doc else None,
            "execution_id": existing.id,
            "status": existing.status,
            "idempotent": True,
        })

    thumbnail_b64 = _generate_thumbnail(file_bytes, content_type)

    doc_record = await db.document.create(data={
        "tenant_id": tenant_id,
        "tool_id": tool.id,
        "document_type": "pending",
        "filename": file.filename,
        "content_type": content_type,
        "file_size_bytes": len(file_bytes),
        "status": "processing",
        "thumbnail_b64": thumbnail_b64,
    })

    execution = await db.execution.create(data={
        "tenant_id": tenant_id,
        "tool_id": tool.id,
        "input_ref": idempotency_key,
        "decision": "pending",
        "confidence": 0.0,
        "status": "queued",
    })

    await db.document.update(
        where={"id": doc_record.id},
        data={"execution_id": execution.id},
    )

    pool = await get_queue_pool()
    await pool.enqueue_job(
        "run_document_intelligence_job",
        execution_id=execution.id,
        tenant_id=tenant_id,
        tool_id=tool.id,
        file_bytes=file_bytes,
        content_type=content_type,
        document_id=doc_record.id,
    )

    _logger.info(
        "doc_intelligence_api_upload_queued",
        extra={
            "tenant_id": tenant_id,
            "tool_id": tool.id,
            "document_id": doc_record.id,
            "execution_id": execution.id,
            "document_filename": file.filename,
            "size_bytes": len(file_bytes),
        },
    )

    return standard_response(data={
        "document_id": doc_record.id,
        "execution_id": execution.id,
        "status": "queued",
    })


@router.get("/tools")
async def list_tools(
    authorization: str = Header(..., alias="Authorization"),
):
    """List active deployed tools for the authenticated tenant."""
    tenant_id, _ = await _resolve_api_key(authorization)
    db = get_db()

    tools = await db.tool.find_many(
        where={"tenant_id": tenant_id, "status": "active"},
        order={"type": "asc"},
    )

    return standard_response(
        data={
            "tools": [
                {
                    "id": t.id,
                    "type": t.type,
                    "autonomy_level": t.autonomy_level,
                    "status": t.status,
                    "version": t.version,
                }
                for t in tools
            ]
        }
    )


@router.get("/approvals")
async def list_approvals(
    authorization: str = Header(..., alias="Authorization"),
    limit: int = Query(20, le=200),
    offset: int = Query(0, ge=0),
):
    """List pending approvals for the authenticated tenant."""
    tenant_id, _ = await _resolve_api_key(authorization)
    db = get_db()

    approvals = await db.approval.find_many(
        where={"tenant_id": tenant_id, "status": "pending"},
        order={"requested_at": "asc"},
        take=limit,
        skip=offset,
        include={"execution": {"include": {"tool": True}}},
    )

    return standard_response(
        data={
            "approvals": [
                {
                    "id": a.id,
                    "tool_id": a.execution.tool_id if a.execution else None,
                    "tool_type": a.execution.tool.type if (a.execution and a.execution.tool) else None,
                    "decision": a.execution.decision if a.execution else None,
                    "confidence": a.execution.confidence if a.execution else None,
                    "reasoning": None,
                    "created_at": a.requested_at.isoformat(),
                    "expires_at": a.expires_at.isoformat(),
                }
                for a in approvals
            ]
        }
    )


@router.post("/approvals/{approval_id}/approve")
async def approve_action(
    approval_id: str,
    authorization: str = Header(..., alias="Authorization"),
):
    """Approve a pending action. Enforces tenant isolation and expiry TTL."""
    tenant_id, _ = await _resolve_api_key(authorization)
    db = get_db()

    approval = await db.approval.find_first(
        where={"id": approval_id, "tenant_id": tenant_id}
    )
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    if approval.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Approval is already '{approval.status}' and cannot be acted on",
        )

    now = datetime.now(UTC)
    expires_at = approval.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if now > expires_at:
        raise HTTPException(status_code=410, detail="Approval has expired")

    await db.approval.update(
        where={"id": approval_id},
        data={"status": "approved", "responded_at": now},
    )
    await db.execution.update(
        where={"id": approval.execution_id},
        data={"decision": "approved"},
    )

    _logger.info(
        "approval_approved_via_api_key",
        extra={"approval_id": approval_id, "tenant_id": tenant_id},
    )

    return standard_response(data={"approval_id": approval_id, "status": "approved"})


@router.post("/approvals/{approval_id}/reject")
async def reject_action(
    approval_id: str,
    authorization: str = Header(..., alias="Authorization"),
):
    """Reject a pending action. Enforces tenant isolation and expiry TTL."""
    tenant_id, _ = await _resolve_api_key(authorization)
    db = get_db()

    approval = await db.approval.find_first(
        where={"id": approval_id, "tenant_id": tenant_id}
    )
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    if approval.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Approval is already '{approval.status}' and cannot be acted on",
        )

    now = datetime.now(UTC)
    expires_at = approval.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if now > expires_at:
        raise HTTPException(status_code=410, detail="Approval has expired")

    await db.approval.update(
        where={"id": approval_id},
        data={"status": "rejected", "responded_at": now},
    )
    await db.execution.update(
        where={"id": approval.execution_id},
        data={"decision": "rejected"},
    )

    _logger.info(
        "approval_rejected_via_api_key",
        extra={"approval_id": approval_id, "tenant_id": tenant_id},
    )

    return standard_response(data={"approval_id": approval_id, "status": "rejected"})


@router.get("/audit")
async def list_audit(
    authorization: str = Header(..., alias="Authorization"),
    limit: int = Query(20, le=200),
    offset: int = Query(0, ge=0),
):
    """Query the audit log for the authenticated tenant."""
    tenant_id, _ = await _resolve_api_key(authorization)
    db = get_db()

    entries, total = await asyncio.gather(
        db.auditlog.find_many(
            where={"tenant_id": tenant_id},
            order={"created_at": "desc"},
            take=limit,
            skip=offset,
        ),
        db.auditlog.count(where={"tenant_id": tenant_id}),
    )

    return standard_response(
        data={
            "entries": [
                {
                    "id": e.id,
                    "actor": e.actor,
                    "action": e.action,
                    "model_version": e.model_version,
                    "created_at": e.created_at.isoformat(),
                    "execution_id": e.execution_id,
                    "reasoning_trace_json": e.reasoning_trace_json,
                }
                for e in entries
            ],
            "total": total,
        }
    )


@router.get("/transactions")
async def list_transactions(
    authorization: str = Header(..., alias="Authorization"),
    limit: int = Query(20, le=200),
    offset: int = Query(0, ge=0),
):
    """List bank transactions for the authenticated tenant."""
    tenant_id, _ = await _resolve_api_key(authorization)
    db = get_db()

    transactions, total = await asyncio.gather(
        db.banktransaction.find_many(
            where={"tenant_id": tenant_id},
            order={"date": "desc"},
            take=limit,
            skip=offset,
        ),
        db.banktransaction.count(where={"tenant_id": tenant_id}),
    )

    return standard_response(
        data={
            "transactions": [
                {
                    "id": t.id,
                    "source": t.source,
                    "amount_minor": t.amount_minor,
                    "currency": t.currency,
                    "merchant_name": t.merchant_name,
                    "description": t.description,
                    "date": t.date.isoformat(),
                    "ai_category": t.ai_category,
                    "status": t.status,
                    "account_id": t.account_id,
                }
                for t in transactions
            ],
            "total": total,
        }
    )


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
    tenant_id, _ = await _resolve_api_key(authorization)
    db = get_db()

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

    # For document intelligence jobs, include the extracted analysis in the response
    document = None
    if execution.tool and execution.tool.type == "document_intelligence":
        doc = await db.document.find_first(
            where={"execution_id": execution_id, "tenant_id": tenant_id}
        )
        if doc:
            document = {
                "id": doc.id,
                "filename": doc.filename,
                "document_type": doc.document_type,
                "status": doc.status,
                "confidence": doc.confidence,
                "extracted_json": doc.extracted_json,
                "flags_json": doc.flags_json,
            }

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
            **({"document": document} if document is not None else {}),
        }
    )
