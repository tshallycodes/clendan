"""
Document Intelligence API — file upload and document list endpoints.
POST /v1/document-intelligence/{tool_id}/upload
GET  /v1/document-intelligence/{tool_id}/documents
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from prisma import Prisma

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


def _serialize_document(doc) -> dict:
    return {
        "id": doc.id,
        "document_type": doc.document_type,
        "filename": doc.filename,
        "content_type": doc.content_type,
        "file_size_bytes": doc.file_size_bytes,
        "uploaded_by": doc.uploaded_by,
        "status": doc.status,
        "decision": doc.decision,
        "confidence": doc.confidence,
        "rule_triggered": doc.rule_triggered,
        "reason": doc.reason,
        "flags_json": doc.flags_json,
        "extracted_json": doc.extracted_json,
        "thumbnail_b64": doc.thumbnail_b64,
        "accounting_write_status": doc.accounting_write_status,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


@router.post("/{tool_id}/upload")
async def upload_document(
    tool_id: str,
    file: UploadFile,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
) -> dict:
    """
    Accept a document upload, generate a thumbnail, create a Document record,
    and enqueue the document_intelligence job for async processing.
    Claude auto-classifies the document as 'receipt' or 'document' during processing.
    """
    tenant_id = current_user.tenant_id
    logger.debug("doc_upload_start", extra={"tenant_id": tenant_id, "tool_id": tool_id, "file_name": file.filename, "content_type": file.content_type})

    content_type = file.content_type or "application/pdf"
    if content_type not in _ALLOWED_CONTENT_TYPES:
        logger.debug("doc_upload_unsupported_content_type", extra={"content_type": content_type})
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type. Allowed: PDF, Word (.docx), PNG, JPG, WebP",
        )

    file_bytes = await file.read()
    logger.debug("doc_upload_file_read", extra={"size_bytes": len(file_bytes), "content_type": content_type})

    if len(file_bytes) > _MAX_FILE_BYTES:
        logger.debug("doc_upload_file_too_large", extra={"size_bytes": len(file_bytes)})
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 10 MB limit",
        )
    if not file_bytes:
        logger.debug("doc_upload_empty_file")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    tool = await db.tool.find_unique(where={"id": tool_id})
    if not tool or tool.tenant_id != tenant_id:
        logger.debug("doc_upload_tool_not_found", extra={"tool_id": tool_id})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")
    if tool.type != "document_intelligence":
        logger.debug("doc_upload_wrong_tool_type", extra={"tool_type": tool.type})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tool is not of type document_intelligence",
        )
    logger.debug("doc_upload_tool_verified", extra={"tool_id": tool_id})

    thumbnail_b64 = _generate_thumbnail(file_bytes, content_type)
    logger.debug("doc_upload_thumbnail_generated", extra={"has_thumbnail": thumbnail_b64 is not None})

    doc_record = await db.document.create(data={
        "tenant_id": tenant_id,
        "tool_id": tool_id,
        "document_type": "pending",
        "filename": file.filename,
        "content_type": content_type,
        "file_size_bytes": len(file_bytes),
        "uploaded_by": current_user.email,
        "status": "processing",
        "thumbnail_b64": thumbnail_b64,
    })
    logger.debug("doc_upload_record_created", extra={"document_id": doc_record.id})

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
    logger.debug("doc_upload_execution_created", extra={"execution_id": execution.id})

    await db.document.update(
        where={"id": doc_record.id},
        data={"execution_id": execution.id},
    )
    logger.debug("doc_upload_execution_linked", extra={"document_id": doc_record.id, "execution_id": execution.id})

    pool = await get_queue_pool()
    await pool.enqueue_job(
        "run_document_intelligence_job",
        execution_id=execution.id,
        tenant_id=tenant_id,
        tool_id=tool_id,
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
            "execution_id": execution.id,
            "file_name": file.filename,
            "size_bytes": len(file_bytes),
        },
    )

    return standard_response(data={
        "document_id": doc_record.id,
        "execution_id": execution.id,
        "status": "processing",
        "thumbnail_b64": thumbnail_b64,
    })


@router.post("/{tool_id}/documents/{document_id}/abort")
async def abort_document(
    tool_id: str,
    document_id: str,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
) -> dict:
    """Mark a processing document as aborted. Does not cancel the arq job if already running,
    but the job's result will land on a record already marked failed."""
    tenant_id = current_user.tenant_id

    doc = await db.document.find_unique(where={"id": document_id})
    if not doc or doc.tenant_id != tenant_id or doc.tool_id != tool_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    await db.document.delete(where={"id": document_id})

    logger.info("document_deleted", extra={"tenant_id": tenant_id, "document_id": document_id, "prior_status": doc.status})
    return standard_response(data={"document_id": document_id, "deleted": True})


@router.get("/{tool_id}/documents")
async def list_documents(
    tool_id: str,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
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
