"""
Document Intelligence API — file upload and document list endpoints.
POST /v1/document-intelligence/{tool_id}/upload
GET  /v1/document-intelligence/{tool_id}/documents
"""
import base64
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.queue.pool import get_queue_pool
from app.tools.document_intelligence import (
    _ALLOWED_CONTENT_TYPES,
    _MAX_FILE_BYTES,
    _generate_thumbnail,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/document-intelligence", tags=["document-intelligence"])

_VALID_DOCUMENT_TYPES = {"invoice", "receipt", "contract"}


def _serialize_document(doc: object) -> dict:
    d = doc.__dict__ if not isinstance(doc, dict) else doc
    return {
        "id": d.get("id"),
        "document_type": d.get("document_type"),
        "filename": d.get("filename"),
        "content_type": d.get("content_type"),
        "file_size_bytes": d.get("file_size_bytes"),
        "uploaded_by": d.get("uploaded_by"),
        "status": d.get("status"),
        "decision": d.get("decision"),
        "confidence": d.get("confidence"),
        "rule_triggered": d.get("rule_triggered"),
        "reason": d.get("reason"),
        "flags_json": d.get("flags_json"),
        "extracted_json": d.get("extracted_json"),
        "thumbnail_b64": d.get("thumbnail_b64"),
        "accounting_write_status": d.get("accounting_write_status"),
        "created_at": d.get("created_at").isoformat() if d.get("created_at") else None,
    }


@router.post("/{tool_id}/upload")
async def upload_document(
    tool_id: str,
    document_type: str,
    file: UploadFile,
    current_user: RequireOrgAuth,
    db=get_db_dep,
) -> dict:
    """
    Accept a document upload, generate a thumbnail, create a Document record,
    and enqueue the document_intelligence job for async processing.
    """
    tenant_id = current_user.tenant_id

    if document_type not in _VALID_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"document_type must be one of: {', '.join(sorted(_VALID_DOCUMENT_TYPES))}",
        )

    content_type = file.content_type or "application/pdf"
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(_ALLOWED_CONTENT_TYPES))}",
        )

    file_bytes = await file.read()
    if len(file_bytes) > _MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 10 MB limit",
        )
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    tool = await db.tool.find_unique(where={"id": tool_id})
    if not tool or tool.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")
    if tool.type != "document_intelligence":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tool is not of type document_intelligence",
        )

    thumbnail_b64 = _generate_thumbnail(file_bytes, content_type)

    doc_record = await db.document.create(data={
        "tenant_id": tenant_id,
        "tool_id": tool_id,
        "document_type": document_type,
        "filename": file.filename,
        "content_type": content_type,
        "file_size_bytes": len(file_bytes),
        "uploaded_by": current_user.email,
        "status": "processing",
        "thumbnail_b64": thumbnail_b64,
    })

    policy_config = tool.config_json if isinstance(tool.config_json, dict) else {}

    idempotency_key = f"doc-upload:{doc_record.id}"
    execution = await db.execution.create(data={
        "tenant_id": tenant_id,
        "tool_id": tool_id,
        "input_ref": idempotency_key,
        "decision": "pending",
        "confidence": 0.0,
        "status": "queued",
        "triggered_by_email": current_user.email,
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
        tool_id=tool_id,
        document_type=document_type,
        file_bytes=file_bytes,
        content_type=content_type,
        policy_config=policy_config,
        document_id=doc_record.id,
    )

    logger.info(
        "document_upload_queued",
        extra={
            "tenant_id": tenant_id,
            "tool_id": tool_id,
            "document_id": doc_record.id,
            "document_type": document_type,
            "filename": file.filename,
        },
    )

    return standard_response(data={
        "document_id": doc_record.id,
        "execution_id": execution.id,
        "status": "processing",
        "thumbnail_b64": thumbnail_b64,
    })


@router.get("/{tool_id}/documents")
async def list_documents(
    tool_id: str,
    current_user: RequireOrgAuth,
    db=get_db_dep,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Return all documents processed by this tool, newest first."""
    tenant_id = current_user.tenant_id

    tool = await db.tool.find_unique(where={"id": tool_id})
    if not tool or tool.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")

    documents = await db.document.find_many(
        where={"tenant_id": tenant_id, "tool_id": tool_id},
        order={"created_at": "desc"},
        take=min(limit, 100),
        skip=offset,
    )

    total = await db.document.count(
        where={"tenant_id": tenant_id, "tool_id": tool_id}
    )

    return standard_response(data={
        "documents": [_serialize_document(doc) for doc in documents],
        "total": total,
        "limit": limit,
        "offset": offset,
    })
