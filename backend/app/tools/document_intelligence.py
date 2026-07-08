"""
Document Intelligence Tool - comprehensive AI analysis of any business document.
Classifies uploads and produces structured analysis: summary, risks, loopholes, improvements.
"""
import asyncio
import base64
import json
import time
from typing import Any

import anthropic
import fitz  # PyMuPDF
from prisma import Json as PrismaJson
from pydantic import BaseModel

from app.audit.logger import write_audit_log
from app.core.config import get_settings
from app.core.db import get_db
from app.core.execution import complete_execution
from app.core.logging import get_logger
from app.queue.pool import push_to_dlq

_logger = get_logger(__name__)

TOOL_TYPE = "document_intelligence"
TOOL_VERSION = 2

_ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/png", "image/jpeg", "image/jpg", "image/webp",
    "image/heic", "image/heif",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

class _ToolPolicy(BaseModel):
    auto_approve_confidence_min: float = 0.80
    flag_keywords: str = ""


def _parse_policy(config_json: dict) -> _ToolPolicy:
    mapped: dict[str, Any] = {}
    if "auto_approve_confidence_min" in config_json:
        mapped["auto_approve_confidence_min"] = float(config_json["auto_approve_confidence_min"]) / 100
    if "flag_keywords" in config_json:
        mapped["flag_keywords"] = str(config_json["flag_keywords"])
    return _ToolPolicy(**mapped)


_CLASSIFY_PROMPT = """Classify this document. Return ONLY valid JSON:
{
  "type": "receipt" or "document" or "error",
  "error_reason": null or one of: "image_unreadable", "empty_document", "no_text_found", "cannot_identify",
  "error_message": null or a human-readable error message in title case
}
receipt = any receipt, proof of purchase, expense claim, transaction record.
document = any business document: contract, NDA, report, letter, policy, financial statement, proposal, invoice, etc.
error = cannot classify. Set error_reason and a clear error_message.
Error reasons: image_unreadable (too blurry/dark), empty_document (blank), no_text_found (no readable text), cannot_identify (unrecognised content).
Return ONLY the JSON object. No markdown, no explanation."""


_DOCUMENT_PROMPT = """Analyse this business document comprehensively. Return ONLY valid JSON:
{
  "document_subtype": one of: contract nda agreement report letter policy financial_statement invoice proposal terms_of_service other,
  "summary": "2-3 paragraph plain English summary",
  "risks": ["specific risk or concern"],
  "loopholes": ["potential loophole or ambiguous clause"],
  "improvements": ["suggested improvement or missing clause"],
  "parties": ["entity or person name"],
  "key_dates": ["date and its significance"],
  "confidence": float 0.0 to 1.0
}
Be thorough but concise. Each item should be a clear, specific statement. Return ONLY the JSON. No markdown."""


def _generate_thumbnail(file_bytes: bytes, content_type: str) -> str | None:
    """Render first page at ~150px width, return as base64 PNG."""
    if content_type == _DOCX_MIME:
        return None
    try:
        if content_type == "application/pdf":
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        else:
            ext = content_type.split("/")[-1].replace("jpg", "jpeg")
            doc = fitz.open(stream=file_bytes, filetype=ext)
        page = doc[0]
        mat = fitz.Matrix(0.12, 0.12)
        pix = page.get_pixmap(matrix=mat)
        return base64.standard_b64encode(pix.tobytes("png")).decode()
    except Exception as exc:
        _logger.warning("thumbnail_generation_failed", extra={"error": str(exc)})
        return None


def _pdf_to_images(pdf_bytes: bytes) -> list[bytes]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    return [page.get_pixmap(dpi=150).tobytes("png") for page in doc]


def _docx_to_text(file_bytes: bytes) -> str:
    try:
        import io
        from docx import Document as DocxDocument
        doc = DocxDocument(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError as exc:
        raise ValueError("python-docx not installed - cannot process Word documents") from exc
    except Exception as exc:
        raise ValueError(f"Failed to read Word document: {exc}") from exc


async def _call_claude_vision(
    file_bytes: bytes,
    content_type: str,
    prompt: str,
    max_tokens: int = 1024,
) -> dict[str, Any]:
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=60.0)

    if content_type == "application/pdf":
        images = _pdf_to_images(file_bytes)
        media_type = "image/png"
    else:
        images = [file_bytes]
        media_type = content_type

    content: list[dict] = []
    for img_bytes in images:
        b64 = base64.standard_b64encode(img_bytes).decode()
        content.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}})
    content.append({"type": "text", "text": prompt})

    last_exc: Exception = RuntimeError("No attempts made")
    for attempt in range(settings.max_agent_attempts):
        try:
            response = await client.messages.create(
                model=settings.claude_model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": content}],
            )
            return json.loads(response.content[0].text)
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            last_exc = exc
            _logger.warning("doc_intel_claude_transient", extra={"attempt": attempt + 1, "error": str(exc)})
            if attempt < settings.max_agent_attempts - 1:
                await asyncio.sleep(settings.backoff_seconds * (attempt + 1))
        except (json.JSONDecodeError, Exception) as exc:
            raise ValueError(f"Claude returned unparseable response: {exc}") from exc

    raise RuntimeError(
        f"Claude API failed after {settings.max_agent_attempts} attempts: {last_exc}"
    ) from last_exc


async def _call_claude_text(text: str, prompt: str, max_tokens: int = 1024) -> dict[str, Any]:
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=60.0)
    user_message = f"{prompt}\n\nDocument text:\n{text[:50000]}"

    last_exc: Exception = RuntimeError("No attempts made")
    for attempt in range(settings.max_agent_attempts):
        try:
            response = await client.messages.create(
                model=settings.claude_model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": user_message}],
            )
            return json.loads(response.content[0].text)
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            last_exc = exc
            _logger.warning("doc_intel_claude_transient", extra={"attempt": attempt + 1, "error": str(exc)})
            if attempt < settings.max_agent_attempts - 1:
                await asyncio.sleep(settings.backoff_seconds * (attempt + 1))
        except (json.JSONDecodeError, Exception) as exc:
            raise ValueError(f"Claude returned unparseable response: {exc}") from exc

    raise RuntimeError(
        f"Claude API failed after {settings.max_agent_attempts} attempts: {last_exc}"
    ) from last_exc


async def _classify_document(file_bytes: bytes, content_type: str) -> dict[str, Any]:
    if content_type == _DOCX_MIME:
        text = _docx_to_text(file_bytes)
        return await _call_claude_text(text, _CLASSIFY_PROMPT, max_tokens=256)

    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=30.0)

    if content_type == "application/pdf":
        pages = _pdf_to_images(file_bytes)
        img_bytes = pages[0] if pages else file_bytes
        media_type = "image/png"
    else:
        img_bytes = file_bytes
        media_type = content_type

    b64 = base64.standard_b64encode(img_bytes).decode()
    last_exc: Exception = RuntimeError("No attempts made")
    for attempt in range(settings.max_agent_attempts):
        try:
            response = await client.messages.create(
                model=settings.claude_model,
                max_tokens=256,
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                    {"type": "text", "text": _CLASSIFY_PROMPT},
                ]}],
            )
            return json.loads(response.content[0].text)
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            last_exc = exc
            if attempt < settings.max_agent_attempts - 1:
                await asyncio.sleep(settings.backoff_seconds * (attempt + 1))
        except (json.JSONDecodeError, Exception) as exc:
            raise ValueError(f"Unparseable classification response: {exc}") from exc

    raise RuntimeError(
        f"Classification failed after {settings.max_agent_attempts} attempts: {last_exc}"
    ) from last_exc



async def _process_document(file_bytes: bytes, content_type: str) -> dict[str, Any]:
    if content_type == _DOCX_MIME:
        text = _docx_to_text(file_bytes)
        data = await _call_claude_text(text, _DOCUMENT_PROMPT, max_tokens=2048)
    else:
        data = await _call_claude_vision(file_bytes, content_type, _DOCUMENT_PROMPT, max_tokens=2048)

    confidence = float(data.get("confidence", 0.0))
    subtype = data.get("document_subtype", "other")
    extracted: dict[str, Any] = {
        "document_subtype": subtype,
        "summary": data.get("summary", ""),
        "risks": data.get("risks", []),
        "loopholes": data.get("loopholes", []),
        "improvements": data.get("improvements", []),
        "parties": data.get("parties", []),
        "key_dates": data.get("key_dates", []),
    }
    return {
        "decision": "analysed",
        "confidence": confidence,
        "reason": f"Document analysed - {subtype.replace('_', ' ')}",
        "extracted": extracted,
    }


async def run_document_intelligence_job(
    ctx: dict,
    *,
    execution_id: str,
    tenant_id: str,
    tool_id: str,
    file_bytes: bytes,
    content_type: str,
    document_id: str | None = None,
    policy_config: dict | None = None,
) -> dict:
    """arq job entry point. Classifies then routes to receipt or document processing.

    policy_config is supplied by the document_received auto-ingest path
    (run_document_received_job); the direct-upload path omits it and the policy is
    read from the tool's tenant-scoped DB config instead.
    """
    db = get_db()
    _start = time.monotonic()
    _logger.debug("doc_intel_job_start", extra={
        "execution_id": execution_id, "tenant_id": tenant_id, "tool_id": tool_id,
        "document_id": document_id, "size_bytes": len(file_bytes), "job_try": ctx.get("job_try", 1),
    })

    try:
        if policy_config is not None:
            policy = _parse_policy(policy_config)
        else:
            tool = await db.tool.find_first(where={"id": tool_id, "tenant_id": tenant_id})
            policy = _parse_policy(tool.config_json if tool and isinstance(tool.config_json, dict) else {})

        classification = await _classify_document(file_bytes, content_type)
        doc_type = classification.get("type", "error")
        _logger.debug("doc_intel_classified", extra={"execution_id": execution_id, "doc_type": doc_type})

        rule_triggered: str | None = None

        if doc_type == "error":
            error_msg = classification.get("error_message") or "Could not read this document"
            result: dict[str, Any] = {
                "document_type": "pending",
                "decision": "classification_failed",
                "confidence": 0.0,
                "reason": error_msg,
                "extracted": {},
            }
        else:
            r = await _process_document(file_bytes, content_type)
            result = {"document_type": "document", **r}

            # Apply policy - keyword check first, then confidence threshold
            if policy.flag_keywords.strip():
                keywords = [kw.strip().lower() for kw in policy.flag_keywords.split(",") if kw.strip()]
                analysis_text = json.dumps(result.get("extracted", {})).lower()
                matched = [kw for kw in keywords if kw in analysis_text]
                if matched:
                    result["decision"] = "approval_required"
                    rule_triggered = f"keyword: {', '.join(matched)}"

            if result["decision"] != "approval_required":
                if result.get("confidence", 0.0) >= policy.auto_approve_confidence_min:
                    result["decision"] = "auto_approved"
                else:
                    result["decision"] = "approval_required"

        # Audit FIRST - if this fails, the operation fails (hard requirement)
        await write_audit_log(
            tenant_id=tenant_id,
            actor=f"tool:{TOOL_TYPE}:v{TOOL_VERSION}",
            action=f"document_processed:{result['document_type']}",
            reasoning_trace={
                "tool_id": tool_id,
                "document_type": result["document_type"],
                "decision": result["decision"],
                "confidence": result["confidence"],
                "reason": result["reason"],
                "rule_triggered": rule_triggered,
                "tool_version": TOOL_VERSION,
            },
            model_version=f"{TOOL_TYPE}-v{TOOL_VERSION}",
            execution_id=execution_id,
        )

        duration_ms = int((time.monotonic() - _start) * 1000)
        await complete_execution(
            db=db, execution_id=execution_id, tool_id=tool_id,
            tenant_id=tenant_id, decision=result["decision"],
            confidence=result["confidence"], duration_ms=duration_ms,
        )

        if document_id:
            try:
                await db.document.update(
                    where={"id": document_id},
                    data={
                        "document_type": result["document_type"],
                        "status": "completed",
                        "decision": result["decision"],
                        "confidence": result["confidence"],
                        "reason": result["reason"],
                        "rule_triggered": rule_triggered,
                        "extracted_json": PrismaJson(result.get("extracted", {})),
                    },
                )
            except Exception as exc:
                _logger.warning("doc_intel_document_update_failed", extra={"document_id": document_id, "error": str(exc)})

        _logger.info("doc_intel_job_completed", extra={
            "execution_id": execution_id, "document_id": document_id,
            "decision": result["decision"], "document_type": result["document_type"],
        })
        return result

    except BaseException as exc:
        _logger.error("doc_intel_job_failed", extra={
            "execution_id": execution_id, "document_id": document_id,
            "error": str(exc), "type": type(exc).__name__, "job_try": ctx.get("job_try", 1),
        })
        try:
            await db.execution.update(where={"id": execution_id}, data={"status": "failed", "decision": "failed"})
        except Exception:
            pass
        if document_id:
            try:
                await db.document.update(where={"id": document_id}, data={"status": "failed"})
            except Exception:
                pass
        if isinstance(exc, Exception) and ctx.get("job_try", 1) >= 3:
            await push_to_dlq(
                job_id=str(ctx.get("job_id", "unknown")),
                function_name="run_document_intelligence_job",
                error=str(exc),
            )
        raise
