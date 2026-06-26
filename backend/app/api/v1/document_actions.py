"""
Document quick-action endpoints.
GET  /v1/documents/{document_id}/export
POST /v1/documents/{document_id}/ask
"""
import json
from datetime import UTC, datetime
from typing import Annotated

import anthropic
from fastapi import APIRouter, Depends, HTTPException, Response, status
from prisma import Prisma
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth

_logger = get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


class AskClenRequest(BaseModel):
    question: str


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

    raw_name = doc.filename or doc.id
    base_name = raw_name.rsplit('.', 1)[0] if '.' in raw_name else raw_name
    return Response(
        content=json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{base_name}.json"'},
    )


@router.post("/{document_id}/ask")
async def ask_clen(
    document_id: str,
    body: AskClenRequest,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
) -> dict:
    """Answer a follow-up question about a completed document using its extracted analysis."""
    tenant_id = current_user.tenant_id

    doc = await db.document.find_unique(where={"id": document_id})
    if not doc or doc.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if doc.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Document must be fully processed before asking questions",
        )

    context_parts: list[str] = [
        f"Filename: {doc.filename or 'unknown'}",
        f"Document type: {doc.document_type}",
        f"Classification: {doc.decision}",
    ]
    if doc.extracted_json and isinstance(doc.extracted_json, dict):
        for key, value in doc.extracted_json.items():
            if isinstance(value, list):
                if value:
                    context_parts.append(f"{key}: {'; '.join(str(v) for v in value)}")
            elif value:
                context_parts.append(f"{key}: {value}")

    document_context = "\n".join(context_parts)

    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    message = await client.messages.create(
        model=settings.claude_model,
        max_tokens=1500,
        system=(
            "You are Clen, an AI assistant for Clendan. "
            "You are answering a follow-up question about a document based on its extracted analysis. "
            "Use the document context to give a specific, accurate, and concise answer. "
            "If you cannot answer based on the available information, say so clearly."
        ),
        messages=[{
            "role": "user",
            "content": f"Document context:\n{document_context}\n\nQuestion: {body.question}",
        }],
    )
    answer: str = message.content[0].text

    _logger.info("doc_intel_ask_clen", extra={"tenant_id": tenant_id, "document_id": document_id})
    return standard_response(data={"answer": answer, "document_id": document_id})
