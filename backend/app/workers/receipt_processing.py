"""
Receipt Processing Worker — parses a receipt image and writes an audit entry.
Sub-agent called by the Orchestrator as a tool.
Flow: parse → policy check → audit → return
"""
import asyncio
import base64
import json
from typing import Any

import anthropic

from app.audit.logger import write_audit_log
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.receipt_parse import ALLOWED_CATEGORIES, ParsedReceipt
from app.queue.pool import push_to_dlq

_logger = get_logger(__name__)

WORKER_TYPE = "receipt_processing"
WORKER_VERSION = 1
MIN_CONFIDENCE = 0.5

_RECEIPT_PROMPT = f"""You are a receipt data extraction system. Extract fields from this receipt image and return ONLY a valid JSON object.

Fields:
- merchant (string): Store or vendor name
- amount_minor (integer): Total amount paid in minor units (multiply decimal by 100 — e.g. £12.50 → 1250)
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


async def execute_receipt_worker(
    *,
    worker_id: str,
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

    # Audit FIRST — operation fails if this cannot be recorded
    await write_audit_log(
        tenant_id=tenant_id,
        actor=f"worker:{WORKER_TYPE}:v{WORKER_VERSION}",
        action="receipt_processed",
        reasoning_trace=reasoning_trace,
        model_version=f"{WORKER_TYPE}-v{WORKER_VERSION}",
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
    worker_id: str,
    file_bytes: bytes,
    content_type: str,
    policy_config: dict,
) -> dict:
    """arq job entry point for receipt processing."""
    from app.core.db import get_db
    db = get_db()
    try:
        result = await execute_receipt_worker(
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
        return result
    except Exception as exc:
        await db.execution.update(
            where={"id": execution_id},
            data={"status": "failed", "decision": "failed"},
        )
        if ctx.get("job_try", 1) >= 3:
            await push_to_dlq(str(ctx.get("job_id", "unknown")), "run_receipt_job", str(exc))
        raise
