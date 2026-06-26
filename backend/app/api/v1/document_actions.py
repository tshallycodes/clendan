"""
Document quick-action endpoints.
POST /v1/documents/{document_id}/flag
GET  /v1/documents/{document_id}/export
POST /v1/documents/{document_id}/push-integration
POST /v1/documents/{document_id}/summarise
"""
from datetime import UTC, datetime, timedelta
from typing import Annotated
import json

import anthropic
from fastapi import APIRouter, Depends, HTTPException, Response, status
from prisma import Prisma
from pydantic import BaseModel

from app.audit.logger import write_audit_log
from app.core.config import get_settings
from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth

_logger = get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])

_VALID_INTEGRATIONS = {"xero", "quickbooks", "freshbooks", "sage", "netsuite"}


class PushIntegrationRequest(BaseModel):
    integration: str


@router.post("/{document_id}/flag")
async def flag_document(
    document_id: str,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
) -> dict:
    """Flag a completed document for human review by creating a pending approval."""
    tenant_id = current_user.tenant_id

    doc = await db.document.find_unique(where={"id": document_id})
    if not doc or doc.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if doc.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only completed documents can be flagged",
        )

    if doc.execution_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Document has no execution to flag",
        )

    existing = await db.approval.find_first(
        where={"execution_id": doc.execution_id, "status": "pending"}
    )
    if existing:
        return standard_response(data={"already_flagged": True})

    approval = await db.approval.create(
        data={
            "tenant_id": tenant_id,
            "execution_id": doc.execution_id,
            "expires_at": datetime.now(UTC) + timedelta(hours=72),
        }
    )

    await write_audit_log(
        tenant_id=tenant_id,
        actor=f"user:{current_user.user_id}",
        action="document_flagged",
        reasoning_trace={
            "document_id": document_id,
            "execution_id": doc.execution_id,
            "approval_id": approval.id,
        },
        model_version="human",
        execution_id=doc.execution_id,
    )

    _logger.info(
        "document_flagged",
        extra={"tenant_id": tenant_id, "document_id": document_id, "approval_id": approval.id},
    )
    return standard_response(data={"approval_id": approval.id})


@router.get("/{document_id}/export")
async def export_document(
    document_id: str,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
) -> Response:
    """Export a document's extracted data as a JSON file download."""
    tenant_id = current_user.tenant_id

    doc = await db.document.find_unique(where={"id": document_id})
    if not doc or doc.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if doc.extracted_json is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No extracted data available",
        )

    payload = {
        "document_id": doc.id,
        "filename": doc.filename,
        "document_type": doc.document_type,
        "decision": doc.decision,
        "extracted": doc.extracted_json,
        "exported_at": datetime.now(UTC).isoformat(),
    }

    filename = doc.filename or doc.id
    return Response(
        content=json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
    )


@router.post("/{document_id}/push-integration")
async def push_document_to_integration(
    document_id: str,
    body: PushIntegrationRequest,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
) -> dict:
    """Mark a completed document as written to an accounting integration."""
    tenant_id = current_user.tenant_id

    if body.integration not in _VALID_INTEGRATIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"integration must be one of: {', '.join(sorted(_VALID_INTEGRATIONS))}",
        )

    doc = await db.document.find_unique(where={"id": document_id})
    if not doc or doc.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if doc.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only completed documents can be pushed to an integration",
        )

    if doc.decision == "blocked":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Blocked documents cannot be pushed to integration",
        )

    if doc.accounting_write_status and ":" in doc.accounting_write_status:
        return standard_response(data={"already_written": True})

    if not doc.tool_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Document has no associated tool",
        )

    tool = await db.tool.find_unique(where={"id": doc.tool_id})
    configured: list[str] = []
    if tool and isinstance(tool.config_json, dict):
        configured = tool.config_json.get("accounting_integrations", []) or []

    if body.integration not in configured:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{body.integration.capitalize()} is not connected. Add it in the tool's Configure drawer first.",
        )

    await db.document.update(
        where={"id": document_id},
        data={"accounting_write_status": f"written:{body.integration}"},
    )

    await write_audit_log(
        tenant_id=tenant_id,
        actor=f"user:{current_user.user_id}",
        action="document_pushed_to_integration",
        reasoning_trace={
            "document_id": document_id,
            "integration": body.integration,
            "document_type": doc.document_type,
            "filename": doc.filename,
        },
        model_version="human",
        execution_id=doc.execution_id,
    )

    _logger.info(
        "document_pushed_to_integration",
        extra={
            "tenant_id": tenant_id,
            "document_id": document_id,
            "integration": body.integration,
        },
    )
    return standard_response(data={"integration": body.integration, "status": "written"})


@router.post("/{document_id}/summarise")
async def summarise_document(
    document_id: str,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
) -> dict:
    """Generate an AI summary of a completed contract document."""
    tenant_id = current_user.tenant_id

    doc = await db.document.find_unique(where={"id": document_id})
    if not doc or doc.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if doc.document_type != "contract":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Summarisation is only available for contracts",
        )

    if doc.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only completed documents can be summarised",
        )

    fields_text: str = ""
    if doc.extracted_json and isinstance(doc.extracted_json, dict):
        fields_text = "\n".join(f"{k}: {v}" for k, v in doc.extracted_json.items())

    system_prompt = (
        "You are Clen, an AI financial assistant for Clendan. "
        "Summarise the following contract in clear, structured prose. "
        "Cover: parties involved, key dates and term, financial obligations, "
        "governing law, and any notable clauses or risks. "
        "Write in a professional but readable tone. "
        "Use markdown headers (##) to structure your response."
    )
    user_message = (
        f"Contract filename: {doc.filename}\n\n"
        f"Extracted fields:\n{fields_text or 'No structured fields extracted.'}"
    )

    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    summary: str = message.content[0].text

    _logger.info(
        "document_summarised",
        extra={"tenant_id": tenant_id, "document_id": document_id},
    )
    return standard_response(data={"summary": summary, "document_id": document_id})
