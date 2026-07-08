import asyncio
import base64
import json
from datetime import datetime, timedelta, UTC
from typing import Any

import anthropic
import fitz  # PyMuPDF
from pydantic import BaseModel

from app.audit.logger import write_audit_log
from app.core.config import get_settings
from app.core.db import get_db
from app.core.execution import complete_execution
from app.core.logging import get_logger
from app.models.invoice_parse import ParsedInvoice
from app.policy.engine import Decision, PolicyResult, evaluate_invoice_policy
from app.queue.pool import push_to_dlq

_logger = get_logger(__name__)

TOOL_TYPE = "invoice_processing"
TOOL_VERSION = 1


class _ToolPolicy(BaseModel):
    verified_suppliers: list[str] = []
    allowed_currencies: list[str] = ["GBP", "USD", "EUR"]
    auto_threshold_minor: int = 50_000
    block_threshold_minor: int = 1_000_000
    min_ocr_confidence: float = 0.85
    duplicate_window_days: int = 90
    max_invoice_age_days: int = 180
    approval_tier_1_minor: int = 100_000
    approval_tier_2_minor: int = 1_000_000


def _parse_policy(raw: dict[str, Any]) -> _ToolPolicy:
    return _ToolPolicy(**{k: v for k, v in raw.items() if k in _ToolPolicy.model_fields})


_INVOICE_PROMPT = """You are an invoice data extraction system. Extract fields from this invoice and return ONLY a valid JSON object.

Fields:
- vendor (string): Vendor/supplier company name
- invoice_number (string): Invoice reference number
- line_items (array): [{description, quantity, unit_price_minor, total_minor}] - all amounts in minor units (pence/cents, multiply decimal by 100)
- amount_minor (integer): Total invoice amount in minor units
- currency (string): ISO 4217 code (GBP, USD, EUR, etc.)
- due_date (string|null): ISO 8601 date YYYY-MM-DD or null
- vat_minor (integer|null): VAT/tax amount in minor units or null
- po_number (string|null): Purchase order number or null
- confidence (float): Extraction confidence 0.0–1.0

Return ONLY the JSON object. No markdown, no explanation."""


def _pdf_to_images(pdf_bytes: bytes) -> list[bytes]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    return [page.get_pixmap(dpi=150).tobytes("png") for page in doc]


async def _extract_invoice(file_bytes: bytes, content_type: str) -> ParsedInvoice:
    """Call Claude vision to extract invoice fields. Retries on transient API errors."""
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    if content_type == "application/pdf":
        images = _pdf_to_images(file_bytes)
        media_type = "image/png"
    else:
        images = [file_bytes]
        media_type = content_type

    content: list[dict] = []
    for img_bytes in images:
        b64 = base64.standard_b64encode(img_bytes).decode()
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        })
    content.append({"type": "text", "text": _INVOICE_PROMPT})

    last_exc: Exception = RuntimeError("No attempts made")
    for attempt in range(settings.max_agent_attempts):
        try:
            response = await client.messages.create(
                model=settings.claude_model,
                max_tokens=2048,
                messages=[{"role": "user", "content": content}],
            )
            raw_text = response.content[0].text
            data = json.loads(raw_text)
            return ParsedInvoice(**data)
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            last_exc = exc
            _logger.warning(
                "invoice_extract_transient_error",
                extra={"attempt": attempt + 1, "error": str(exc)},
            )
            if attempt < settings.max_agent_attempts - 1:
                await asyncio.sleep(settings.backoff_seconds * (attempt + 1))
        except (json.JSONDecodeError, Exception) as exc:
            raise ValueError(f"Claude returned unparseable response: {exc}") from exc

    raise RuntimeError(
        f"Claude API failed after {settings.max_agent_attempts} attempts: {last_exc}"
    ) from last_exc


async def _check_duplicate(
    tenant_id: str,
    invoice_number: str,
    duplicate_window_days: int,
) -> bool:
    """Return True if this invoice_number already exists within the duplicate window."""
    db = get_db()
    cutoff = datetime.now(UTC) - timedelta(days=duplicate_window_days)
    existing = await db.invoice.find_first(
        where={
            "tenant_id": tenant_id,
            "invoice_number": invoice_number,
            "created_at": {"gte": cutoff},
        }
    )
    return existing is not None


async def execute_invoice_tool(
    *,
    tool_id: str,
    tenant_id: str,
    execution_id: str,
    file_bytes: bytes,
    content_type: str,
    policy_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Full invoice processing flow:
    parse → duplicate check → policy → audit → accounting write → return

    Audit is written BEFORE any external write (CLAUDE.md hard requirement).
    Accounting write only occurs for AUTO_APPROVED decisions.
    """
    policy = _parse_policy(policy_config)

    # 1. Parse invoice with Claude vision
    parsed = await _extract_invoice(file_bytes, content_type)

    # 2. Duplicate detection (DB check - cannot be done in pure policy function)
    is_duplicate = await _check_duplicate(
        tenant_id=tenant_id,
        invoice_number=parsed.invoice_number,
        duplicate_window_days=policy.duplicate_window_days,
    )

    # 3. Policy evaluation (OCR confidence, duplicate, age, amount, currency, supplier)
    invoice_date = parsed.due_date  # best proxy for invoice age; use due_date if issue_date absent
    policy_result: PolicyResult = evaluate_invoice_policy(
        amount_minor=parsed.amount_minor,
        currency=parsed.currency,
        vendor=parsed.vendor,
        verified_suppliers=policy.verified_suppliers,
        allowed_currencies=policy.allowed_currencies,
        auto_threshold_minor=policy.auto_threshold_minor,
        block_threshold_minor=policy.block_threshold_minor,
        ocr_confidence=parsed.confidence,
        min_ocr_confidence=policy.min_ocr_confidence,
        is_duplicate=is_duplicate,
        invoice_date=invoice_date,
        max_invoice_age_days=policy.max_invoice_age_days,
        approval_tier_1_minor=policy.approval_tier_1_minor,
        approval_tier_2_minor=policy.approval_tier_2_minor,
    )

    reasoning_trace: dict[str, Any] = {
        "parsed_invoice": parsed.model_dump(mode="json"),
        "is_duplicate": is_duplicate,
        "policy_decision": policy_result.decision,
        "policy_reason": policy_result.reason,
        "policy_rule_triggered": policy_result.rule_triggered,
        "accounting_write_performed": False,
        "tool_version": TOOL_VERSION,
    }

    # 4. Audit FIRST - operation fails if audit cannot be recorded (CLAUDE.md hard requirement)
    await write_audit_log(
        tenant_id=tenant_id,
        actor=f"tool:{TOOL_TYPE}:v{TOOL_VERSION}",
        action="invoice_processed",
        reasoning_trace=reasoning_trace,
        model_version=f"{TOOL_TYPE}-v{TOOL_VERSION}",
        execution_id=execution_id,
    )

    # 5. Accounting write AFTER audit - only for auto-approved invoices
    if policy_result.decision == Decision.AUTO_APPROVED:
        try:
            from app.integrations.quickbooks.write import write_bill_to_quickbooks
            qb_result = await write_bill_to_quickbooks(
                tenant_id=tenant_id,
                execution_id=execution_id,
                vendor=parsed.vendor,
                invoice_number=parsed.invoice_number,
                amount_minor=parsed.amount_minor,
                currency=parsed.currency,
                due_date=parsed.due_date,
                line_items=[item.model_dump() for item in (parsed.line_items or [])],
            )
            reasoning_trace["accounting_write_performed"] = True
            reasoning_trace["qb_bill_id"] = qb_result["qb_bill_id"]
        except Exception as exc:
            _logger.warning(
                "invoice_qb_write_failed",
                extra={"tenant_id": tenant_id, "execution_id": execution_id, "error": str(exc)},
            )

    return {
        "decision": policy_result.decision,
        "reason": policy_result.reason,
        "rule_triggered": policy_result.rule_triggered,
        "parsed_invoice": parsed.model_dump(mode="json"),
        "confidence": parsed.confidence,
    }


async def run_invoice_job(
    ctx: dict,
    *,
    execution_id: str,
    tenant_id: str,
    tool_id: str,
    file_bytes: bytes,
    content_type: str,
    policy_config: dict,
) -> dict:
    """arq job entry point. Updates the Execution record and creates Approval if needed."""
    db = get_db()
    try:
        result = await execute_invoice_tool(
            tool_id=tool_id,
            tenant_id=tenant_id,
            execution_id=execution_id,
            file_bytes=file_bytes,
            content_type=content_type,
            policy_config=policy_config,
        )

        await complete_execution(
            db=db, execution_id=execution_id, tool_id=tool_id,
            tenant_id=tenant_id, decision=result["decision"],
            confidence=result["confidence"], duration_ms=0,
        )
        return result

    except Exception as exc:
        _logger.error(
            "invoice_job_failed",
            extra={"execution_id": execution_id, "error": str(exc)},
        )
        await db.execution.update(
            where={"id": execution_id},
            data={"status": "failed", "decision": "failed"},
        )
        job_try = ctx.get("job_try", 1)
        if job_try >= 3:
            await push_to_dlq(
                job_id=str(ctx.get("job_id", "unknown")),
                function_name="run_invoice_job",
                error=str(exc),
            )
        raise
