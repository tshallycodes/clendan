"""
Document Intelligence Tool — auto-classifies uploads as receipts or documents.
Receipts: extract fields and auto-push to configured accounting integrations.
Documents: comprehensive AI analysis (summary, risks, loopholes, improvements).
"""
import asyncio
import base64
import json
import time
from typing import Any

import anthropic
import fitz  # PyMuPDF
from prisma import Json as PrismaJson

from app.audit.logger import write_audit_log
from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.queue.pool import push_to_dlq

_logger = get_logger(__name__)

TOOL_TYPE = "document_intelligence"
WORKER_VERSION = 2

_ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/png", "image/jpeg", "image/jpg", "image/webp",
    "image/heic", "image/heif",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

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

_RECEIPT_PROMPT = """Extract all data from this receipt. Return ONLY valid JSON:
{
  "merchant": "store or vendor name",
  "amount_minor": integer total paid in minor currency units (multiply decimal by 100),
  "currency": "ISO 4217 code e.g. GBP USD EUR",
  "date": "YYYY-MM-DD" or null,
  "category": one of: food_and_drink travel accommodation software office_supplies utilities entertainment professional_services fuel other,
  "confidence": float 0.0 to 1.0
}
Return ONLY the JSON. No markdown, no explanation."""

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
        raise ValueError("python-docx not installed — cannot process Word documents") from exc
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


async def _process_receipt(
    file_bytes: bytes,
    content_type: str,
    accounting_integrations: list[str],
    tenant_id: str,
    execution_id: str,
) -> dict[str, Any]:
    if content_type == _DOCX_MIME:
        text = _docx_to_text(file_bytes)
        data = await _call_claude_text(text, _RECEIPT_PROMPT, max_tokens=512)
    else:
        data = await _call_claude_vision(file_bytes, content_type, _RECEIPT_PROMPT, max_tokens=512)

    merchant = data.get("merchant", "Unknown")
    amount_minor = int(data.get("amount_minor", 0))
    currency = data.get("currency", "GBP")
    date_str = data.get("date")
    category = data.get("category", "other")
    confidence = float(data.get("confidence", 0.0))
    extracted: dict[str, Any] = {
        "merchant": merchant,
        "amount_minor": amount_minor,
        "currency": currency,
        "date": date_str,
        "category": category,
    }

    _logger.info("doc_intel_push_start", extra={
        "execution_id": execution_id,
        "tenant_id": tenant_id,
        "accounting_integrations": accounting_integrations,
        "merchant": merchant,
        "amount_minor": amount_minor,
        "currency": currency,
        "date": date_str,
    })

    if not accounting_integrations:
        _logger.warning("doc_intel_push_no_integrations", extra={
            "execution_id": execution_id, "tenant_id": tenant_id,
        })
        return {
            "decision": "push_failed",
            "confidence": confidence,
            "reason": "No accounting integrations configured — add one in tool settings",
            "extracted": extracted,
            "accounting_write_status": None,
        }

    ref = f"RCPT-{execution_id[:8].upper()}"
    write_results: list[str] = []
    for integration in accounting_integrations:
        _logger.info("doc_intel_push_attempt", extra={
            "execution_id": execution_id, "integration": integration, "ref": ref,
        })
        try:
            if integration == "xero":
                from app.integrations.xero.write import create_bill
                await create_bill(
                    tenant_id=tenant_id, vendor=merchant, invoice_number=ref,
                    amount_minor=amount_minor, currency=currency, due_date=date_str,
                )
            elif integration == "quickbooks":
                from app.integrations.quickbooks.write import write_bill_to_quickbooks
                await write_bill_to_quickbooks(
                    tenant_id=tenant_id, execution_id=execution_id, vendor=merchant,
                    invoice_number=ref, amount_minor=amount_minor, currency=currency,
                    due_date=date_str, line_items=[],
                )
            elif integration == "freshbooks":
                from app.integrations.freshbooks.write import create_bill as fb_create
                await fb_create(
                    tenant_id=tenant_id, vendor=merchant, invoice_number=ref,
                    amount_minor=amount_minor, currency=currency,
                )
            else:
                _logger.warning("doc_intel_unknown_integration", extra={
                    "execution_id": execution_id, "integration": integration,
                })
                write_results.append(f"unsupported:{integration}")
                continue
            _logger.info("doc_intel_push_ok", extra={
                "execution_id": execution_id, "integration": integration,
            })
            write_results.append(f"written:{integration}")
        except Exception as exc:
            import httpx as _httpx
            response_body: str | None = None
            status_code: int | None = None
            if isinstance(exc, _httpx.HTTPStatusError):
                status_code = exc.response.status_code
                try:
                    response_body = exc.response.text
                except Exception:
                    response_body = "<unreadable>"
            _logger.error(
                "doc_intel_push_failed",
                extra={
                    "execution_id": execution_id,
                    "integration": integration,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "http_status": status_code,
                    "response_body": response_body,
                },
            )
            write_results.append(f"failed:{integration}")

    accounting_write_status = ",".join(write_results)
    all_failed = all(not r.startswith("written:") for r in write_results)
    decision = "push_failed" if all_failed else "auto_pushed"
    names = [i.capitalize() for i in accounting_integrations]
    reason = "Push failed for all integrations" if all_failed else f"Pushed to {', '.join(names)}"
    return {
        "decision": decision,
        "confidence": confidence,
        "reason": reason,
        "extracted": extracted,
        "accounting_write_status": accounting_write_status,
    }


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
        "reason": f"Document analysed — {subtype.replace('_', ' ')}",
        "extracted": extracted,
        "accounting_write_status": None,
    }


async def run_document_intelligence_job(
    ctx: dict,
    *,
    execution_id: str,
    tenant_id: str,
    tool_id: str,
    file_bytes: bytes,
    content_type: str,
    policy_config: dict,
    document_id: str | None = None,
) -> dict:
    """arq job entry point. Classifies then routes to receipt or document processing."""
    db = get_db()
    _start = time.monotonic()
    accounting_integrations: list[str] = (
        policy_config.get("accounting_integrations", []) or []
        if isinstance(policy_config, dict) else []
    )
    _logger.debug("doc_intel_job_start", extra={
        "execution_id": execution_id, "tenant_id": tenant_id, "tool_id": tool_id,
        "document_id": document_id, "size_bytes": len(file_bytes), "job_try": ctx.get("job_try", 1),
    })

    try:
        classification = await _classify_document(file_bytes, content_type)
        doc_type = classification.get("type", "error")
        _logger.debug("doc_intel_classified", extra={"execution_id": execution_id, "doc_type": doc_type})

        if doc_type == "error":
            error_msg = classification.get("error_message") or "Could not classify this document"
            result: dict[str, Any] = {
                "document_type": "pending",
                "decision": "classification_failed",
                "confidence": 0.0,
                "reason": error_msg,
                "extracted": {},
                "accounting_write_status": None,
            }
        elif doc_type == "receipt":
            r = await _process_receipt(file_bytes, content_type, accounting_integrations, tenant_id, execution_id)
            result = {"document_type": "receipt", **r}
        else:
            r = await _process_document(file_bytes, content_type)
            result = {"document_type": "document", **r}

        # Audit FIRST — if this fails, the operation fails (hard requirement)
        await write_audit_log(
            tenant_id=tenant_id,
            actor=f"tool:{TOOL_TYPE}:v{WORKER_VERSION}",
            action=f"document_processed:{result['document_type']}",
            reasoning_trace={
                "tool_id": tool_id,
                "document_type": result["document_type"],
                "decision": result["decision"],
                "confidence": result["confidence"],
                "reason": result["reason"],
                "accounting_write_status": result.get("accounting_write_status"),
                "tool_version": WORKER_VERSION,
            },
            model_version=f"{TOOL_TYPE}-v{WORKER_VERSION}",
            execution_id=execution_id,
        )

        duration_ms = int((time.monotonic() - _start) * 1000)
        await db.execution.update(
            where={"id": execution_id},
            data={
                "status": "completed",
                "decision": result["decision"],
                "confidence": result["confidence"],
                "duration_ms": duration_ms,
            },
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
                        "extracted_json": PrismaJson(result.get("extracted", {})),
                        "accounting_write_status": result.get("accounting_write_status"),
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
