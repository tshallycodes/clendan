"""
Invoice & Receipt Processing Tool (internal type: document_intelligence).
Classifies each financial document and routes it: invoice -> bill (AP), receipt -> expense
(Spend Control). Anything that is not an invoice or receipt is recorded with no action.
"""
import asyncio
import base64
import json
import time
from datetime import datetime
from typing import Any

import anthropic
import fitz  # PyMuPDF
from prisma import Json as PrismaJson

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

_CLASSIFY_PROMPT = """Classify this document. Return ONLY valid JSON:
{
  "type": "receipt" or "invoice" or "other" or "error",
  "error_reason": null or one of: "image_unreadable", "empty_document", "no_text_found", "cannot_identify",
  "error_message": null or a human-readable error message in title case
}
receipt = any receipt, proof of purchase, expense claim, transaction record.
invoice = a supplier/vendor invoice or bill requesting payment - has an invoice number, line items, and a payable total.
other = any document that is not a receipt or invoice (contract, report, letter, statement, etc.). This tool only processes financial documents, so these are recorded with no action.
error = cannot classify. Set error_reason and a clear error_message.
Error reasons: image_unreadable (too blurry/dark), empty_document (blank), no_text_found (no readable text), cannot_identify (unrecognised content).
Return ONLY the JSON object. No markdown, no explanation."""


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



_INVOICE_STATUS_BY_DECISION = {
    "auto_approved": "approved",
    "approval_required": "pending",
    "blocked": "blocked",
}


async def _create_native_invoice(
    db, tenant_id: str, document_id: str | None, parsed: dict, decision: str
) -> None:
    """Persist a native Invoice row from the parsed invoice so the payable is immediately
    visible/queryable and duplicate detection works. Best-effort - never fails the job."""
    due = parsed.get("due_date")
    due_dt = None
    if due:
        try:
            due_dt = datetime.fromisoformat(str(due))
        except ValueError:
            due_dt = None
    try:
        await db.invoice.create(data={
            "tenant_id": tenant_id,
            "vendor": parsed.get("vendor") or "Unknown",
            "invoice_number": parsed.get("invoice_number") or "",
            "amount_minor": int(parsed.get("amount_minor") or 0),
            "currency": parsed.get("currency") or "GBP",
            "due_date": due_dt,
            "status": _INVOICE_STATUS_BY_DECISION.get(decision, "pending"),
            "raw_document_ref": document_id,
            "parsed_json": PrismaJson(parsed),
        })
    except Exception as exc:
        _logger.warning("doc_intel_native_invoice_create_failed", extra={"error": str(exc)})


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
            raw_config = policy_config
        else:
            tool = await db.tool.find_first(where={"id": tool_id, "tenant_id": tenant_id})
            raw_config = tool.config_json if tool and isinstance(tool.config_json, dict) else {}

        classification = await _classify_document(file_bytes, content_type)
        doc_type = classification.get("type", "error")
        _logger.debug("doc_intel_classified", extra={"execution_id": execution_id, "doc_type": doc_type})

        rule_triggered: str | None = None
        audit_needed = True  # invoices audit themselves via execute_invoice_tool

        if doc_type == "error":
            error_msg = classification.get("error_message") or "Could not read this document"
            result: dict[str, Any] = {
                "document_type": "pending",
                "decision": "classification_failed",
                "confidence": 0.0,
                "reason": error_msg,
                "extracted": {},
            }
        elif doc_type == "invoice":
            # Real AP processing: extract payable fields, run invoice policy, and (on
            # auto-approve) write the bill to the connected ERP. Reuses the invoice tool's
            # flow, which writes its own audit before the ERP write - so we skip the
            # generic audit below to avoid a duplicate entry.
            from app.tools.invoice_processing import execute_invoice_tool
            inv = await execute_invoice_tool(
                tool_id=tool_id,
                tenant_id=tenant_id,
                execution_id=execution_id,
                file_bytes=file_bytes,
                content_type=content_type,
                policy_config=raw_config,
            )
            parsed = inv.get("parsed_invoice", {}) or {}
            result = {
                "document_type": "invoice",
                "decision": inv["decision"],
                "confidence": inv["confidence"],
                "reason": inv["reason"],
                "extracted": parsed,
            }
            rule_triggered = inv.get("rule_triggered")
            audit_needed = False
            await _create_native_invoice(db, tenant_id, document_id, parsed, inv["decision"])
        elif doc_type == "receipt":
            # Receipt -> expense. Reuses the receipt tool's flow, which writes its own
            # audit before any action, so we skip the generic audit below.
            from app.tools.receipt_processing import execute_receipt_tool
            rec = await execute_receipt_tool(
                tool_id=tool_id,
                tenant_id=tenant_id,
                execution_id=execution_id,
                file_bytes=file_bytes,
                content_type=content_type,
                policy_config=raw_config,
            )
            result = {
                "document_type": "receipt",
                "decision": rec["decision"],
                "confidence": rec["confidence"],
                "reason": rec["reason"],
                "extracted": rec.get("parsed_receipt", {}) or {},
            }
            audit_needed = False
        else:
            # Not an invoice or receipt - this tool only processes financial documents.
            result = {
                "document_type": "other",
                "decision": "no_action",
                "confidence": 1.0,
                "reason": "Not an invoice or receipt - no financial action taken.",
                "extracted": {},
            }

        # Audit FIRST - if this fails, the operation fails (hard requirement).
        # Invoices/receipts are already audited inside their own tool (audit_needed=False).
        if audit_needed:
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
