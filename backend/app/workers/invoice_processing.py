import asyncio
import base64
import json
from datetime import datetime, timedelta, UTC
from typing import Any

import anthropic
import fitz  # PyMuPDF

from app.audit.logger import write_audit_log
from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.models.invoice_parse import ParsedInvoice
from app.policy.engine import Decision, PolicyResult, evaluate_policy
from app.queue.pool import push_to_dlq

_logger = get_logger(__name__)

WORKER_TYPE = "invoice_processing"
WORKER_VERSION = 1

_INVOICE_PROMPT = """You are an invoice data extraction system. Extract fields from this invoice and return ONLY a valid JSON object.

Fields:
- vendor (string): Vendor/supplier company name
- invoice_number (string): Invoice reference number
- line_items (array): [{description, quantity, unit_price_minor, total_minor}] — all amounts in minor units (pence/cents, multiply decimal by 100)
- amount_minor (integer): Total invoice amount in minor units
- currency (string): ISO 4217 code (GBP, USD, EUR, etc.)
- due_date (string|null): ISO 8601 date YYYY-MM-DD or null
- vat_minor (integer|null): VAT/tax amount in minor units or null
- po_number (string|null): Purchase order number or null
- confidence (float): Extraction confidence 0.0–1.0

Return ONLY the JSON object. No markdown, no explanation."""

MIN_CONFIDENCE = 0.5


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
            if attempt < settings.max_agent_attempts - 1:
                await asyncio.sleep(settings.backoff_seconds * (attempt + 1))
        except (json.JSONDecodeError, Exception) as exc:
            raise ValueError(f"Claude returned unparseable response: {exc}") from exc

    raise RuntimeError(f"Claude API failed after {settings.max_agent_attempts} attempts: {last_exc}") from last_exc


async def _mock_accounting_write(parsed: ParsedInvoice, tenant_id: str, execution_id: str) -> None:
    """Simulated accounting write. Phase 3 replaces this with the real QuickBooks client."""
    # Log only the execution_id trace reference — no financial amounts in logs
    _logger.info(
        "mock_accounting_write",
        extra={"tenant_id": tenant_id, "execution_id": execution_id},
    )


async def execute_invoice_worker(
    *,
    worker_id: str,
    tenant_id: str,
    execution_id: str,
    file_bytes: bytes,
    content_type: str,
    policy_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Full invoice processing flow:
    parse → policy check (includes supplier validation) → audit → accounting write → return

    Audit is written BEFORE any external write (CLAUDE.md hard requirement).
    Accounting write only occurs for AUTO_APPROVED decisions.
    """
    # 1. Parse
    parsed = await _extract_invoice(file_bytes, content_type)
    if parsed.confidence < MIN_CONFIDENCE:
        raise ValueError(
            f"Invoice extraction confidence {parsed.confidence} is below minimum {MIN_CONFIDENCE}"
        )

    # 2. Policy check (currency + amount + supplier)
    policy_result: PolicyResult = evaluate_policy(
        amount_minor=parsed.amount_minor,
        currency=parsed.currency,
        vendor=parsed.vendor,
        verified_suppliers=policy_config.get("verified_suppliers", []),
        allowed_currencies=policy_config.get("allowed_currencies", ["GBP", "USD", "EUR"]),
        auto_threshold_minor=policy_config.get("auto_threshold_minor", 50000),
        block_threshold_minor=policy_config.get("block_threshold_minor", 1_000_000),
    )

    reasoning_trace: dict[str, Any] = {
        "parsed_invoice": parsed.model_dump(mode="json"),
        "policy_decision": policy_result.decision,
        "policy_reason": policy_result.reason,
        "policy_rule_triggered": policy_result.rule_triggered,
        "accounting_write_performed": False,
    }

    # 3. Audit FIRST — operation fails if audit cannot be recorded
    await write_audit_log(
        tenant_id=tenant_id,
        actor=f"worker:{WORKER_TYPE}:v{WORKER_VERSION}",
        action="invoice_processed",
        reasoning_trace=reasoning_trace,
        model_version=f"{WORKER_TYPE}-v{WORKER_VERSION}",
        execution_id=execution_id,
    )

    # 4. Accounting write AFTER audit — only for auto-approved invoices
    if policy_result.decision == Decision.AUTO_APPROVED:
        await _mock_accounting_write(parsed, tenant_id, execution_id)

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
    worker_id: str,
    file_bytes: bytes,
    content_type: str,
    policy_config: dict,
) -> dict:
    """arq job entry point. Updates the Execution record and creates Approval if needed."""
    db = get_db()
    try:
        result = await execute_invoice_worker(
            worker_id=worker_id,
            tenant_id=tenant_id,
            execution_id=execution_id,
            file_bytes=file_bytes,
            content_type=content_type,
            policy_config=policy_config,
        )

        await db.execution.update(
            where={"id": execution_id},
            data={
                "status": "completed",
                "decision": result["decision"],
                "confidence": result["confidence"],
            },
        )

        if result["decision"] == Decision.APPROVAL_REQUIRED:
            settings = get_settings()
            await db.approval.create(
                data={
                    "tenant_id": tenant_id,
                    "execution_id": execution_id,
                    "expires_at": datetime.now(UTC) + timedelta(seconds=settings.approval_ttl_seconds),
                }
            )

        return result

    except Exception as exc:
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
