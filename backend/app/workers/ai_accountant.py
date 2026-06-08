"""
AI Accountant Worker — categorises bank transactions and matches them to invoices.
Sub-agent called by the Financial Orchestrator as a tool.
Follows mandatory execution flow: receive → classify → execute → policy check → output → audit.
"""
import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Any

import anthropic
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger, get_trace_id
from app.queue.pool import push_to_dlq

logger = get_logger(__name__)

ALLOWED_CATEGORIES = {
    "advertising", "bank_fees", "consulting", "equipment", "insurance",
    "legal", "meals", "office_supplies", "payroll", "rent", "software",
    "tax", "travel", "utilities", "other",
}


class _WorkerPolicy(BaseModel):
    auto_confidence_threshold: float = 0.85
    approve_confidence_threshold: float = 0.50
    max_batch_size: int = 500


def _parse_policy(raw: dict[str, Any]) -> _WorkerPolicy:
    return _WorkerPolicy(**{k: v for k, v in raw.items() if k in _WorkerPolicy.model_fields})


@dataclass
class TransactionResult:
    transaction_id: str
    ai_category: str
    matched_invoice_id: str | None
    confidence: float
    reasoning: str
    decision: str  # auto | pending | blocked


@dataclass
class WorkerResult:
    execution_id: str
    decision: str
    confidence: float
    results: list[TransactionResult]
    reasoning_trace: str


class AIAccountantWorker:
    """
    Categorises bank transactions and matches them to invoices using Claude.
    Called by the Orchestrator as a tool — never invoked directly from routes.
    """

    async def run(
        self,
        transaction_ids: list[str],
        tenant_id: str,
        worker_id: str,
        policy_config: dict[str, Any] | None = None,
    ) -> WorkerResult:
        start = time.monotonic()
        trace_id = get_trace_id()
        db = get_db()
        policy = _parse_policy(policy_config or {})

        # STEP 1: Receive + validate
        if not transaction_ids:
            raise ValueError("transaction_ids cannot be empty")
        if not tenant_id:
            raise ValueError("tenant_id required")

        capped = transaction_ids[: policy.max_batch_size]

        # STEP 2: Classify — fetch transactions scoped to tenant
        transactions = await db.banktransaction.find_many(
            where={"id": {"in": capped}, "tenant_id": tenant_id}
        )
        if not transactions:
            raise ValueError("No transactions found for tenant")

        invoices = await db.invoice.find_many(
            where={"tenant_id": tenant_id, "status": {"in": ["pending", "approved"]}},
            take=50,
            order={"created_at": "desc"},
        )

        # STEP 3: Execute — call Claude with retry
        results, reasoning_trace = await self._call_claude(transactions, invoices, policy)

        # STEP 4: Policy check — validate every result
        policy_violations: list[str] = []
        for r in results:
            if r.ai_category not in ALLOWED_CATEGORIES:
                policy_violations.append(
                    f"Invalid category '{r.ai_category}' for txn {r.transaction_id}"
                )
            if not (0.0 <= r.confidence <= 1.0):
                policy_violations.append(
                    f"Confidence {r.confidence} out of range for txn {r.transaction_id}"
                )

        if policy_violations:
            logger.warning("ai_accountant_policy_violations: %s", policy_violations)
            overall_decision = "blocked"
            overall_confidence = 0.0
        else:
            confidences = [r.confidence for r in results]
            overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            if overall_confidence >= policy.auto_confidence_threshold:
                overall_decision = "auto"
            elif overall_confidence >= policy.approve_confidence_threshold:
                overall_decision = "pending"
            else:
                overall_decision = "blocked"

        duration_ms = int((time.monotonic() - start) * 1000)

        # STEP 5: Output — write results to DB only if not blocked
        if overall_decision != "blocked":
            for r in results:
                await db.banktransaction.update(
                    where={"id": r.transaction_id},
                    data={
                        "ai_category": r.ai_category,
                        "matched_invoice_id": r.matched_invoice_id,
                        "status": "matched" if r.matched_invoice_id else "categorised",
                    },
                )

        # STEP 6: Write Execution record
        execution = await db.execution.create(
            data={
                "tenant_id": tenant_id,
                "worker_id": worker_id,
                "input_ref": json.dumps({"transaction_ids": transaction_ids, "trace_id": trace_id}),
                "decision": overall_decision,
                "confidence": overall_confidence,
                "status": "completed",
                "duration_ms": duration_ms,
            }
        )

        # STEP 7: Audit — append-only, must succeed or operation fails
        await db.auditlog.create(
            data={
                "tenant_id": tenant_id,
                "execution_id": execution.id,
                "actor": f"worker:{worker_id}",
                "action": "ai_accountant:categorise_and_match",
                "reasoning_trace_json": {
                    "trace_id": trace_id,
                    "reasoning": reasoning_trace,
                    "results": [
                        {
                            "transaction_id": r.transaction_id,
                            "ai_category": r.ai_category,
                            "matched_invoice_id": r.matched_invoice_id,
                            "confidence": r.confidence,
                            "reasoning": r.reasoning,
                        }
                        for r in results
                    ],
                    "policy_violations": policy_violations,
                },
                "model_version": get_settings().claude_model,
            }
        )

        logger.info(
            "ai_accountant_complete",
            extra={
                "tenant_id": tenant_id,
                "txn_count": len(results),
                "decision": overall_decision,
                "confidence": overall_confidence,
                "duration_ms": duration_ms,
            },
        )

        return WorkerResult(
            execution_id=execution.id,
            decision=overall_decision,
            confidence=overall_confidence,
            results=results,
            reasoning_trace=reasoning_trace,
        )

    async def _call_claude(
        self,
        transactions: list,
        invoices: list,
        policy: _WorkerPolicy,
    ) -> tuple[list[TransactionResult], str]:
        settings = get_settings()
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

        txn_list = [
            {
                "id": t.id,
                "amount_minor": t.amount_minor,
                "currency": t.currency,
                "merchant_name": t.merchant_name,
                "description": t.description,
                "date": t.date.isoformat() if t.date else "",
                "plaid_category": t.category,
            }
            for t in transactions
        ]

        invoice_list = [
            {
                "id": i.id,
                "vendor": i.vendor,
                "amount_minor": i.amount_minor,
                "currency": i.currency,
                "invoice_number": i.invoice_number,
            }
            for i in invoices
        ]

        prompt = f"""You are an AI accountant. Categorise each bank transaction and match it to an invoice if one exists.

TRANSACTIONS:
{json.dumps(txn_list, indent=2)}

OPEN INVOICES:
{json.dumps(invoice_list, indent=2)}

ALLOWED CATEGORIES: {", ".join(sorted(ALLOWED_CATEGORIES))}

For each transaction, return a JSON array with this exact shape:
[
  {{
    "transaction_id": "<id>",
    "ai_category": "<category from allowed list>",
    "matched_invoice_id": "<invoice id or null>",
    "confidence": <0.0-1.0>,
    "reasoning": "<one sentence>"
  }}
]

Rules:
- amount_minor is in cents (100 = $1.00). Use this when matching amounts to invoices.
- matched_invoice_id must be null if no invoice matches within 10% amount tolerance and similar vendor name.
- confidence reflects how certain you are of both the category and match.
- Return ONLY the JSON array — no markdown, no explanation."""

        last_exc: Exception = RuntimeError("No attempts made")
        for attempt in range(settings.max_agent_attempts):
            try:
                message = await client.messages.create(
                    model=settings.claude_model,
                    max_tokens=2048,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = message.content[0].text.strip()
                parsed = json.loads(raw)
                break
            except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
                last_exc = exc
                logger.warning(
                    "ai_accountant_transient_error",
                    extra={"attempt": attempt + 1, "error": str(exc)},
                )
                if attempt < settings.max_agent_attempts - 1:
                    await asyncio.sleep(settings.backoff_seconds * (attempt + 1))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "Claude returned non-JSON output for AI Accountant"
                ) from exc
        else:
            raise RuntimeError(
                f"Claude API failed after {settings.max_agent_attempts} attempts: {last_exc}"
            ) from last_exc

        results: list[TransactionResult] = []
        for item in parsed:
            if not item.get("transaction_id"):
                logger.warning("ai_accountant_missing_transaction_id in Claude response item")
                continue
            category = item.get("ai_category", "other").lower().strip()
            if category not in ALLOWED_CATEGORIES:
                category = "other"
            confidence = float(item.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))

            if confidence >= policy.auto_confidence_threshold:
                decision = "auto"
            elif confidence >= policy.approve_confidence_threshold:
                decision = "pending"
            else:
                decision = "blocked"

            results.append(TransactionResult(
                transaction_id=item["transaction_id"],
                ai_category=category,
                matched_invoice_id=item.get("matched_invoice_id"),
                confidence=confidence,
                reasoning=item.get("reasoning", ""),
                decision=decision,
            ))

        return results, raw


async def run_ai_accountant(
    ctx: dict,
    transaction_ids: list[str],
    tenant_id: str,
    worker_id: str,
    policy_config: dict | None = None,
) -> dict:
    """arq job wrapper for the AI Accountant Worker."""
    worker = AIAccountantWorker()
    try:
        result = await worker.run(
            transaction_ids=transaction_ids,
            tenant_id=tenant_id,
            worker_id=worker_id,
            policy_config=policy_config or {},
        )
        return {
            "execution_id": result.execution_id,
            "decision": result.decision,
            "confidence": result.confidence,
            "transactions_processed": len(result.results),
        }
    except Exception as exc:
        logger.error(
            "ai_accountant_job_failed",
            extra={"tenant_id": tenant_id, "error": str(exc)},
        )
        job_try = ctx.get("job_try", 1)
        if job_try >= 3:
            await push_to_dlq(
                job_id=str(ctx.get("job_id", "unknown")),
                function_name="run_ai_accountant",
                error=str(exc),
            )
        raise
