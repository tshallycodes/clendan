"""
Document Intelligence Tool — unified invoice, receipt, and contract processor.
Sub-agent called by the Orchestrator as a tool.
Flow: receive → classify doc type → extract → policy check → audit → store → return
"""
import asyncio
import base64
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import anthropic
import fitz  # PyMuPDF
from pydantic import BaseModel

from app.audit.logger import write_audit_log
from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.policy.engine import Decision
from app.queue.pool import push_to_dlq

_logger = get_logger(__name__)

TOOL_TYPE = "document_intelligence"
WORKER_VERSION = 1

_ALLOWED_CONTENT_TYPES = {
    "application/pdf", "image/png", "image/jpeg", "image/jpg", "image/webp",
}
_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


class _ToolPolicy(BaseModel):
    auto_approve_threshold: int = 50_000
    po_match_required: bool = True
    po_tolerance_pct: float = 0.03
    duplicate_window_days: int = 90
    max_invoice_age_days: int = 180
    new_vendor_flag_enabled: bool = True
    approval_tier_1_limit: int = 100_000
    approval_tier_2_limit: int = 1_000_000
    receipt_required_above: int = 2_500
    submission_deadline_days: int = 30
    ocr_confidence_min: float = 0.82
    duplicate_receipt_window_days: int = 365
    auto_approve_receipt_below: int = 1_000
    contract_extraction_enabled: bool = True
    accounting_integrations: list[str] = []


def _parse_policy(raw: dict[str, Any]) -> _ToolPolicy:
    return _ToolPolicy(**{k: v for k, v in raw.items() if k in _ToolPolicy.model_fields})


def _generate_thumbnail(file_bytes: bytes, content_type: str) -> str | None:
    """Render document first page at ~150px width, return as base64 PNG."""
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


_INVOICE_PROMPT = """You are an invoice data extraction system. Extract fields and return ONLY a valid JSON object.

Fields:
- vendor (string): Vendor/supplier company name
- invoice_number (string): Invoice reference number
- amount_minor (integer): Total amount in minor units (pence/cents — multiply decimal by 100)
- currency (string): ISO 4217 code (GBP, USD, EUR, etc.)
- due_date (string|null): ISO 8601 YYYY-MM-DD or null
- vat_minor (integer|null): VAT in minor units or null
- po_number (string|null): Purchase order number or null
- confidence (float): Extraction confidence 0.0–1.0

Return ONLY the JSON. No markdown, no explanation."""

_RECEIPT_PROMPT = """You are a receipt data extraction system. Extract fields and return ONLY a valid JSON object.

Fields:
- merchant (string): Store or vendor name
- amount_minor (integer): Total paid in minor units (multiply decimal by 100)
- currency (string): ISO 4217 code
- date (string|null): ISO 8601 YYYY-MM-DD or null
- category (string): One of: travel, meals, accommodation, office, equipment, other
- confidence (float): Extraction confidence 0.0–1.0

Return ONLY the JSON. No markdown, no explanation."""

_CONTRACT_PROMPT = """You are a contract data extraction system. Extract key fields and return ONLY a valid JSON object.

Fields:
- counterparty (string): Other party name in the contract
- contract_type (string): E.g. service_agreement, nda, supply_agreement, employment, lease, other
- effective_date (string|null): ISO 8601 YYYY-MM-DD or null
- expiry_date (string|null): ISO 8601 YYYY-MM-DD or null
- payment_terms (string|null): E.g. "Net 30", "Monthly", "Upfront" or null
- obligations (array): List of key obligation strings (max 5)
- amounts (array): List of {description, amount_minor, currency} for monetary values
- governing_law (string|null): Jurisdiction or null
- auto_renewal (boolean): Does the contract auto-renew?
- confidence (float): Extraction confidence 0.0–1.0

Return ONLY the JSON. No markdown, no explanation."""


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


async def _quick_classify(file_bytes: bytes, content_type: str) -> str | None:
    """
    Single-attempt, first-page-only classification.
    Returns 'invoice', 'receipt', or 'contract', or None if uncertain / Claude unavailable.
    Failure is non-fatal — caller should allow the upload to proceed if None is returned.
    """
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=30.0)

    try:
        if content_type == "application/pdf":
            pages = _pdf_to_images(file_bytes)
            img_bytes = pages[0] if pages else file_bytes
            media_type = "image/png"
        else:
            img_bytes = file_bytes
            media_type = content_type

        b64 = base64.standard_b64encode(img_bytes).decode()
        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=10,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                    {"type": "text", "text": "Is this document an invoice, receipt, or contract? Reply with exactly one word: invoice, receipt, or contract."},
                ],
            }],
        )
        word = response.content[0].text.strip().lower().rstrip(".")
        if word in ("invoice", "receipt", "contract"):
            return word
    except Exception as exc:
        _logger.warning("doc_intel_quick_classify_failed", extra={"error": str(exc)})
    return None


async def _check_duplicate_invoice(tenant_id: str, invoice_number: str, window_days: int) -> bool:
    db = get_db()
    cutoff = datetime.now(UTC) - timedelta(days=window_days)
    existing = await db.invoice.find_first(
        where={"tenant_id": tenant_id, "invoice_number": invoice_number, "created_at": {"gte": cutoff}}
    )
    return existing is not None


async def _write_to_accounting(
    tenant_id: str,
    execution_id: str,
    accounting_integrations: list[str],
    document_type: str,
    extracted: dict[str, Any],
) -> str:
    """Write auto-approved invoice to each selected accounting integration. Returns aggregate write status."""
    if not accounting_integrations or document_type != "invoice":
        return "skipped"

    statuses: list[str] = []
    for integration in accounting_integrations:
        if integration == "quickbooks":
            try:
                from app.integrations.quickbooks.write import write_bill_to_quickbooks
                await write_bill_to_quickbooks(
                    tenant_id=tenant_id,
                    execution_id=execution_id,
                    vendor=extracted.get("vendor", "unknown"),
                    invoice_number=extracted.get("invoice_number", "unknown"),
                    amount_minor=int(extracted.get("amount_minor", 0)),
                    currency=extracted.get("currency", "GBP"),
                    due_date=extracted.get("due_date"),
                    line_items=[],
                )
                statuses.append("written")
            except Exception as exc:
                _logger.warning("doc_intel_qb_write_failed", extra={"tenant_id": tenant_id, "error": str(exc)})
                statuses.append("failed")
        else:
            _logger.info(
                "doc_intel_accounting_write_skipped",
                extra={"integration": integration, "reason": "write_not_implemented"},
            )
            statuses.append("skipped")

    if "written" in statuses:
        return "written"
    if "failed" in statuses:
        return "failed"
    return "skipped"


async def _process_invoice(
    file_bytes: bytes,
    content_type: str,
    policy: _ToolPolicy,
    tenant_id: str,
) -> dict[str, Any]:
    data = await _call_claude_vision(file_bytes, content_type, _INVOICE_PROMPT, max_tokens=1024)

    vendor = data.get("vendor", "unknown")
    invoice_number = data.get("invoice_number", "unknown")
    amount_minor = int(data.get("amount_minor", 0))
    currency = data.get("currency", "GBP")
    confidence = float(data.get("confidence", 0.0))
    due_date_str = data.get("due_date")
    po_number = data.get("po_number")

    flags: list[str] = []
    decision = Decision.AUTO_APPROVED.value
    rule_triggered: str | None = None

    if confidence < policy.ocr_confidence_min:
        decision = Decision.APPROVAL_REQUIRED.value
        rule_triggered = "low_ocr_confidence"
        flags.append(f"OCR confidence {confidence:.2f} below minimum {policy.ocr_confidence_min}")

    is_duplicate = await _check_duplicate_invoice(tenant_id, invoice_number, policy.duplicate_window_days)
    if is_duplicate:
        decision = Decision.BLOCKED.value
        rule_triggered = rule_triggered or "duplicate_invoice"
        flags.append(f"Duplicate invoice {invoice_number} within {policy.duplicate_window_days}-day window")

    if due_date_str and decision != Decision.BLOCKED.value:
        try:
            due_date_obj = datetime.fromisoformat(due_date_str).date()
            age_days = (datetime.now(UTC).date() - due_date_obj).days
            if age_days > policy.max_invoice_age_days:
                if decision == Decision.AUTO_APPROVED.value:
                    decision = Decision.APPROVAL_REQUIRED.value
                rule_triggered = rule_triggered or "invoice_too_old"
                flags.append(f"Invoice is {age_days} days old — max is {policy.max_invoice_age_days}")
        except (ValueError, AttributeError):
            pass

    if policy.po_match_required and not po_number and decision == Decision.AUTO_APPROVED.value:
        decision = Decision.APPROVAL_REQUIRED.value
        rule_triggered = rule_triggered or "po_match_required"
        flags.append("PO match required but no PO number found")

    if decision == Decision.AUTO_APPROVED.value:
        if amount_minor > policy.approval_tier_2_limit:
            decision = Decision.APPROVAL_REQUIRED.value
            rule_triggered = rule_triggered or "tier_2_approval"
            flags.append(f"Amount exceeds tier 2 limit ({policy.approval_tier_2_limit // 100} major units)")
        elif amount_minor > policy.approval_tier_1_limit:
            decision = Decision.APPROVAL_REQUIRED.value
            rule_triggered = rule_triggered or "tier_1_approval"
            flags.append(f"Amount exceeds tier 1 limit ({policy.approval_tier_1_limit // 100} major units)")
        elif amount_minor > policy.auto_approve_threshold:
            decision = Decision.APPROVAL_REQUIRED.value
            rule_triggered = rule_triggered or "above_auto_threshold"
            flags.append(f"Amount exceeds auto-approve threshold ({policy.auto_approve_threshold // 100} major units)")

    if not is_duplicate:
        db = get_db()
        due_date_parsed = None
        if due_date_str:
            try:
                due_date_parsed = datetime.fromisoformat(due_date_str)
            except ValueError:
                pass
        await db.invoice.create(data={
            "tenant_id": tenant_id,
            "vendor": vendor,
            "invoice_number": invoice_number,
            "amount_minor": amount_minor,
            "currency": currency,
            "due_date": due_date_parsed,
            "status": decision,
        })

    extracted = {
        "vendor": vendor,
        "invoice_number": invoice_number,
        "amount_minor": amount_minor,
        "currency": currency,
        "due_date": due_date_str,
        "po_number": po_number,
    }
    return {
        "document_type": "invoice",
        "decision": decision,
        "confidence": confidence,
        "rule_triggered": rule_triggered,
        "reason": flags[0] if flags else "All policy checks passed",
        "flags": flags,
        "extracted": extracted,
    }


async def _process_receipt(
    file_bytes: bytes,
    content_type: str,
    policy: _ToolPolicy,
) -> dict[str, Any]:
    data = await _call_claude_vision(file_bytes, content_type, _RECEIPT_PROMPT, max_tokens=512)

    merchant = data.get("merchant", "unknown")
    amount_minor = int(data.get("amount_minor", 0))
    currency = data.get("currency", "GBP")
    date_str = data.get("date")
    category = data.get("category", "other")
    confidence = float(data.get("confidence", 0.0))

    flags: list[str] = []
    decision = Decision.AUTO_APPROVED.value
    rule_triggered: str | None = None

    if confidence < policy.ocr_confidence_min:
        decision = Decision.APPROVAL_REQUIRED.value
        rule_triggered = "low_ocr_confidence"
        flags.append(f"OCR confidence {confidence:.2f} below minimum {policy.ocr_confidence_min}")

    if amount_minor > policy.auto_approve_receipt_below and decision == Decision.AUTO_APPROVED.value:
        decision = Decision.APPROVAL_REQUIRED.value
        rule_triggered = rule_triggered or "above_auto_approve_receipt"
        flags.append(f"Amount exceeds auto-approve threshold ({policy.auto_approve_receipt_below // 100} major units)")

    if date_str:
        try:
            receipt_date = datetime.fromisoformat(date_str).date()
            age_days = (datetime.now(UTC).date() - receipt_date).days
            if age_days > policy.submission_deadline_days and decision != Decision.BLOCKED.value:
                if decision == Decision.AUTO_APPROVED.value:
                    decision = Decision.APPROVAL_REQUIRED.value
                rule_triggered = rule_triggered or "submission_deadline"
                flags.append(f"Receipt is {age_days} days old — deadline is {policy.submission_deadline_days} days")
        except (ValueError, AttributeError):
            pass

    return {
        "document_type": "receipt",
        "decision": decision,
        "confidence": confidence,
        "rule_triggered": rule_triggered,
        "reason": flags[0] if flags else "All policy checks passed",
        "flags": flags,
        "extracted": {
            "merchant": merchant,
            "amount_minor": amount_minor,
            "currency": currency,
            "date": date_str,
            "category": category,
        },
    }


async def _process_contract(
    file_bytes: bytes,
    content_type: str,
    policy: _ToolPolicy,
) -> dict[str, Any]:
    if not policy.contract_extraction_enabled:
        return {
            "document_type": "contract",
            "decision": Decision.APPROVAL_REQUIRED.value,
            "confidence": 0.0,
            "rule_triggered": "contract_extraction_disabled",
            "reason": "Contract extraction is disabled in tool config",
            "flags": ["Contract extraction disabled"],
            "extracted": {},
        }

    data = await _call_claude_vision(file_bytes, content_type, _CONTRACT_PROMPT, max_tokens=2048)
    confidence = float(data.get("confidence", 0.0))

    return {
        "document_type": "contract",
        "decision": Decision.APPROVAL_REQUIRED.value,
        "confidence": confidence,
        "rule_triggered": "contract_requires_review",
        "reason": "Contracts always require human sign-off before any action is taken",
        "flags": ["Contract extraction complete — human review required"],
        "extracted": {
            "counterparty": data.get("counterparty"),
            "contract_type": data.get("contract_type"),
            "effective_date": data.get("effective_date"),
            "expiry_date": data.get("expiry_date"),
            "payment_terms": data.get("payment_terms"),
            "obligations": data.get("obligations", []),
            "amounts": data.get("amounts", []),
            "governing_law": data.get("governing_law"),
            "auto_renewal": data.get("auto_renewal", False),
        },
    }


async def execute_document_intelligence_tool(
    *,
    tool_id: str,
    tenant_id: str,
    execution_id: str,
    document_type: str,
    file_bytes: bytes,
    content_type: str,
    policy_config: dict[str, Any],
    document_id: str | None = None,
) -> dict[str, Any]:
    """
    Document Intelligence flow:
    classify doc type → extract → policy check → audit → store Document record → return
    Audit is written BEFORE the execution record is updated (hard requirement).
    """
    policy = _parse_policy(policy_config)
    db = get_db()

    if not file_bytes:
        result: dict[str, Any] = {
            "document_type": document_type,
            "decision": Decision.APPROVAL_REQUIRED.value,
            "confidence": 0.0,
            "rule_triggered": "no_document_provided",
            "reason": "No document bytes provided — manual review required",
            "flags": ["No document attached"],
            "extracted": {},
        }
    elif document_type == "receipt":
        result = await _process_receipt(file_bytes, content_type, policy)
    elif document_type == "contract":
        result = await _process_contract(file_bytes, content_type, policy)
    else:
        result = await _process_invoice(file_bytes, content_type, policy, tenant_id)

    # Accounting write for auto-approved invoices — before audit so outcome is in the trace
    accounting_status = "skipped"
    if result["decision"] == Decision.AUTO_APPROVED.value:
        accounting_status = await _write_to_accounting(
            tenant_id=tenant_id,
            execution_id=execution_id,
            accounting_integrations=policy.accounting_integrations,
            document_type=document_type,
            extracted=result.get("extracted", {}),
        )

    reasoning_trace: dict[str, Any] = {
        "tool_id": tool_id,
        "document_type": document_type,
        "decision": result["decision"],
        "confidence": result["confidence"],
        "rule_triggered": result.get("rule_triggered"),
        "reason": result["reason"],
        "flags": result.get("flags", []),
        "extracted": result.get("extracted", {}),
        "accounting_write_status": accounting_status,
        "tool_version": WORKER_VERSION,
    }

    # Audit FIRST — operation fails if audit cannot be recorded (hard requirement)
    await write_audit_log(
        tenant_id=tenant_id,
        actor=f"tool:{TOOL_TYPE}:v{WORKER_VERSION}",
        action=f"document_processed:{document_type}",
        reasoning_trace=reasoning_trace,
        model_version=f"{TOOL_TYPE}-v{WORKER_VERSION}",
        execution_id=execution_id,
    )

    # Update Document record if one exists for this run
    if document_id:
        try:
            await db.document.update(
                where={"id": document_id},
                data={
                    "status": "completed",
                    "decision": result["decision"],
                    "confidence": result["confidence"],
                    "rule_triggered": result.get("rule_triggered"),
                    "reason": result["reason"],
                    "flags_json": result.get("flags", []),
                    "extracted_json": result.get("extracted", {}),
                    "accounting_write_status": accounting_status,
                },
            )
        except Exception as exc:
            _logger.warning("doc_intel_document_record_update_failed", extra={"document_id": document_id, "error": str(exc)})

    result["accounting_write_status"] = accounting_status
    return result


async def run_document_intelligence_job(
    ctx: dict,
    *,
    execution_id: str,
    tenant_id: str,
    tool_id: str,
    document_type: str,
    file_bytes: bytes,
    content_type: str,
    policy_config: dict,
    document_id: str | None = None,
) -> dict:
    """arq job entry point. Updates Execution record and creates Approval if needed."""
    db = get_db()
    try:
        result = await execute_document_intelligence_tool(
            tool_id=tool_id,
            tenant_id=tenant_id,
            execution_id=execution_id,
            document_type=document_type,
            file_bytes=file_bytes,
            content_type=content_type,
            policy_config=policy_config,
            document_id=document_id,
        )

        await db.execution.update(
            where={"id": execution_id},
            data={
                "status": "completed",
                "decision": result["decision"],
                "confidence": result["confidence"],
            },
        )

        if result["decision"] == Decision.APPROVAL_REQUIRED.value:
            settings = get_settings()
            existing = await db.approval.find_first(where={"execution_id": execution_id})
            if not existing:
                await db.approval.create(data={
                    "tenant_id": tenant_id,
                    "execution_id": execution_id,
                    "expires_at": datetime.now(UTC) + timedelta(seconds=settings.approval_ttl_seconds),
                })

        return result

    except BaseException as exc:
        _logger.error(
            "document_intelligence_job_failed",
            extra={"execution_id": execution_id, "error": str(exc), "type": type(exc).__name__},
        )
        try:
            await db.execution.update(
                where={"id": execution_id},
                data={"status": "failed", "decision": "failed"},
            )
        except Exception:
            pass
        if document_id:
            try:
                await db.document.update(
                    where={"id": document_id},
                    data={"status": "failed"},
                )
            except Exception:
                pass
        if isinstance(exc, Exception):
            job_try = ctx.get("job_try", 1)
            if job_try >= 3:
                await push_to_dlq(
                    job_id=str(ctx.get("job_id", "unknown")),
                    function_name="run_document_intelligence_job",
                    error=str(exc),
                )
        raise
