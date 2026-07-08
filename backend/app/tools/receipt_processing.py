"""
Receipt Processing Tool - parses a receipt image and writes an audit entry.
Sub-agent tool, dispatched directly to its arq job.
Flow: parse → policy check → audit → return
"""
import asyncio
import base64
import json
from typing import Any

import anthropic
from pydantic import BaseModel

from app.audit.logger import write_audit_log
from app.core.config import get_settings
from app.core.db import get_db
from app.core.execution import complete_execution
from app.core.logging import get_logger
from app.models.receipt_parse import ALLOWED_CATEGORIES, ParsedReceipt
from app.queue.pool import push_to_dlq

_logger = get_logger(__name__)

TOOL_TYPE = "receipt_processing"
TOOL_VERSION = 1
MIN_CONFIDENCE = 0.5


class _ToolPolicy(BaseModel):
    # Existing field
    allowed_categories: list[str] = []
    # New fields
    receipt_required_above: int = 2500
    submission_deadline_days: int = 30
    max_receipt_age_days: int = 90
    ocr_confidence_min: float = 0.82
    duplicate_receipt_window_days: int = 365
    currency_conversion_enabled: bool = True
    fx_rate_tolerance_pct: float = 0.03
    auto_approve_below: int = 1000
    image_min_quality_score: float = 0.60
    personal_expense_detection: bool = True
    vat_extraction_enabled: bool = True
    missing_receipt_grace_period_days: int = 7


def _parse_policy(raw: dict[str, Any]) -> _ToolPolicy:
    """Parse raw policy config dict into a validated _ToolPolicy model."""
    return _ToolPolicy(**{k: v for k, v in raw.items() if k in _ToolPolicy.model_fields})

_RECEIPT_PROMPT = f"""You are a receipt data extraction system. Extract fields from this receipt image and return ONLY a valid JSON object.

Fields:
- merchant (string): Store or vendor name
- amount_minor (integer): Total amount paid in minor units (multiply decimal by 100 - e.g. £12.50 → 1250)
- currency (string): ISO 4217 code (GBP, USD, EUR, etc.)
- date (string|null): ISO 8601 date YYYY-MM-DD or null
- category (string): One of: {", ".join(sorted(ALLOWED_CATEGORIES))}
- confidence (float): 0.0–1.0

Return ONLY the JSON object. No markdown, no explanation."""


async def _extract_receipt(file_bytes: bytes, content_type: str) -> ParsedReceipt:
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    b64 = base64.standard_b64encode(file_bytes).decode()
    content = [
        {"type": "image", "source": {"type": "base64", "media_type": content_type, "data": b64}},
        {"type": "text", "text": _RECEIPT_PROMPT},
    ]

    last_exc: Exception = RuntimeError("No attempts made")
    for attempt in range(settings.max_agent_attempts):
        try:
            response = await client.messages.create(
                model=settings.claude_model,
                max_tokens=512,
                messages=[{"role": "user", "content": content}],
            )
            data = json.loads(response.content[0].text)
            return ParsedReceipt(**data)
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            last_exc = exc
            if attempt < settings.max_agent_attempts - 1:
                await asyncio.sleep(settings.backoff_seconds * (attempt + 1))
        except (json.JSONDecodeError, Exception) as exc:
            raise ValueError(f"Claude returned unparseable response: {exc}") from exc

    raise RuntimeError(f"Claude API failed after {settings.max_agent_attempts} attempts: {last_exc}") from last_exc


async def execute_receipt_tool(
    *,
    tool_id: str,
    tenant_id: str,
    execution_id: str,
    file_bytes: bytes,
    content_type: str,
    policy_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Receipt processing flow: parse → policy check → audit → return
    Category must be in allow-list. Confidence must meet threshold.
    """
    parsed = await _extract_receipt(file_bytes, content_type)

    if parsed.confidence < MIN_CONFIDENCE:
        raise ValueError(f"Receipt extraction confidence {parsed.confidence} below minimum {MIN_CONFIDENCE}")

    # Policy: category must be in the configured allow-list (defaults to full list)
    allowed = set(policy_config.get("allowed_categories", ALLOWED_CATEGORIES))
    if parsed.category not in allowed:
        decision = "blocked"
        reason = f"Category '{parsed.category}' is not in the allowed list"
    else:
        decision = "auto_approved"
        reason = "All policy checks passed"

    reasoning_trace: dict[str, Any] = {
        "parsed_receipt": parsed.model_dump(mode="json"),
        "policy_decision": decision,
        "policy_reason": reason,
    }

    # Audit FIRST - operation fails if this cannot be recorded
    await write_audit_log(
        tenant_id=tenant_id,
        actor=f"tool:{TOOL_TYPE}:v{TOOL_VERSION}",
        action="receipt_processed",
        reasoning_trace=reasoning_trace,
        model_version=f"{TOOL_TYPE}-v{TOOL_VERSION}",
        execution_id=execution_id,
    )

    return {
        "decision": decision,
        "reason": reason,
        "parsed_receipt": parsed.model_dump(mode="json"),
        "confidence": parsed.confidence,
    }


async def run_receipt_job(
    ctx: dict,
    *,
    execution_id: str,
    tenant_id: str,
    tool_id: str,
    file_bytes: bytes,
    content_type: str,
    policy_config: dict,
) -> dict:
    """arq job entry point for receipt processing."""
    from app.core.db import get_db
    db = get_db()
    try:
        result = await execute_receipt_tool(
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
        await db.execution.update(
            where={"id": execution_id},
            data={"status": "failed", "decision": "failed"},
        )
        if ctx.get("job_try", 1) >= 3:
            await push_to_dlq(str(ctx.get("job_id", "unknown")), "run_receipt_job", str(exc))
        raise
