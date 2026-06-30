"""
AI Accountant Tool — categorises bank transactions and matches them to invoices.
Sub-agent called by the Financial Orchestrator as a tool.
Follows mandatory execution flow: receive → classify → execute → policy check → output → audit.
"""
import asyncio
import json
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import anthropic
from pydantic import BaseModel

from app.audit.logger import write_audit_log
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


class _ToolPolicy(BaseModel):
    auto_confidence_threshold: float = 0.85
    approve_confidence_threshold: float = 0.50
    max_batch_size: int = 500
    lookback_days: int = 30
    learn_from_corrections: bool = True
    strict_coa_mode: bool = True
    max_correction_examples: int = 10
    close_run_day_of_month: int = 1
    payroll_keywords: str = "payroll, salary, wages"


def _parse_policy(raw: dict[str, Any]) -> _ToolPolicy:
    mapped: dict[str, Any] = {}
    # Confidence values are stored as percentages (0–100) in config; convert to 0–1 for comparisons
    if "auto_categorise_confidence_min" in raw:
        mapped["auto_confidence_threshold"] = float(raw["auto_categorise_confidence_min"]) / 100
    if "human_review_confidence_min" in raw:
        mapped["approve_confidence_threshold"] = float(raw["human_review_confidence_min"]) / 100
    if "bulk_categorise_batch_size" in raw:
        mapped["max_batch_size"] = int(raw["bulk_categorise_batch_size"])
    if "learn_from_corrections" in raw:
        mapped["learn_from_corrections"] = bool(raw["learn_from_corrections"])
    if "strict_coa_mode" in raw:
        mapped["strict_coa_mode"] = bool(raw["strict_coa_mode"])
    if "max_correction_examples" in raw:
        mapped["max_correction_examples"] = int(raw["max_correction_examples"])
    if "close_run_day_of_month" in raw:
        mapped["close_run_day_of_month"] = int(raw["close_run_day_of_month"])
    if "payroll_keywords" in raw:
        mapped["payroll_keywords"] = str(raw["payroll_keywords"])
    return _ToolPolicy(**mapped)


@dataclass
class TransactionResult:
    transaction_id: str
    ai_category: str
    matched_invoice_id: str | None
    confidence: float
    reasoning: str
    decision: str  # auto | pending | blocked


@dataclass
class ToolResult:
    execution_id: str
    decision: str
    confidence: float
    results: list[TransactionResult]
    reasoning_trace: str


class AIAccountantTool:
    """
    Categorises bank transactions and matches them to invoices using Claude.
    Called by the Orchestrator as a tool — never invoked directly from routes.
    """

    async def run(
        self,
        transaction_ids: list[str],
        tenant_id: str,
        tool_id: str,
        policy_config: dict[str, Any] | None = None,
        execution_id: str | None = None,
    ) -> ToolResult:
        start = time.monotonic()
        trace_id = get_trace_id()
        db = get_db()
        policy = _parse_policy(policy_config or {})

        # STEP 1: Receive + validate
        logger.info(
            "ai_accountant_start",
            extra={
                "execution_id": execution_id,
                "tenant_id": tenant_id,
                "tool_id": tool_id,
                "transaction_count": len(transaction_ids),
            },
        )
        if not transaction_ids:
            raise ValueError("transaction_ids cannot be empty")
        if not tenant_id:
            raise ValueError("tenant_id required")

        capped = transaction_ids[: policy.max_batch_size]

        # STEP 2: Classify — fetch transactions scoped to tenant
        logger.info(
            "ai_accountant_step2_fetch",
            extra={"execution_id": execution_id, "capped_count": len(capped)},
        )
        transactions = await db.banktransaction.find_many(
            where={"id": {"in": capped}, "tenant_id": tenant_id}
        )
        logger.info(
            "ai_accountant_step2_fetched",
            extra={"execution_id": execution_id, "found": len(transactions)},
        )
        if not transactions:
            raise ValueError("No transactions found for tenant")

        invoices = await db.invoice.find_many(
            where={"tenant_id": tenant_id, "status": {"in": ["pending", "approved"]}},
            take=50,
            order={"created_at": "desc"},
        )

        logger.info(
            "ai_accountant_step2b_prior_fetch",
            extra={"execution_id": execution_id, "lookback_days": policy.lookback_days},
        )
        # STEP 2b: Fetch prior-period transactions for category drift detection
        lookback_days = policy.lookback_days
        lookback_cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
        prior_cutoff = lookback_cutoff - timedelta(days=lookback_days)
        prior_transactions = await db.banktransaction.find_many(
            where={
                "tenant_id": tenant_id,
                "date": {"gte": prior_cutoff, "lt": lookback_cutoff},
                "category": {"not": None},
            }
        )
        prior_category_dist: Counter[str] = Counter(
            t.category for t in prior_transactions
        )

        logger.info(
            "ai_accountant_step3_claude_start",
            extra={
                "execution_id": execution_id,
                "transaction_count": len(transactions),
                "invoice_count": len(invoices),
                "prior_txn_count": len(prior_transactions),
            },
        )
        # STEP 3: Execute — call Claude with retry
        results, reasoning_trace = await self._call_claude(
            transactions, invoices, policy, prior_category_dist, tenant_id
        )

        logger.info(
            "ai_accountant_step3_claude_done",
            extra={"execution_id": execution_id, "result_count": len(results)},
        )
        # STEP 3b: Category drift detection
        current_category_dist: Counter[str] = Counter(
            r.ai_category for r in results
        )
        significant_shifts: list[dict] = []
        for cat, current_count in current_category_dist.items():
            prior_count = prior_category_dist.get(cat, 0)
            if prior_count > 0:
                change_pct = (current_count - prior_count) / prior_count * 100
                if abs(change_pct) > 50:
                    significant_shifts.append({
                        "category": cat,
                        "change_pct": round(change_pct, 1),
                        "current": current_count,
                        "prior": prior_count,
                    })
        has_significant_shifts = bool(significant_shifts)

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

        significant_shift_penalty_applied = False
        if policy_violations:
            logger.warning("ai_accountant_policy_violations: %s", policy_violations)
            overall_decision = "blocked"
            overall_confidence = 0.0
        else:
            confidences = [r.confidence for r in results]
            overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            # Reduce confidence when shifts exceed 100% — unusual pattern warrants scrutiny
            if has_significant_shifts and any(
                abs(s["change_pct"]) > 100 for s in significant_shifts
            ):
                overall_confidence = max(0.0, overall_confidence - 0.05)
                significant_shift_penalty_applied = True
            if overall_confidence >= policy.auto_confidence_threshold:
                overall_decision = "auto"
            elif overall_confidence >= policy.approve_confidence_threshold:
                overall_decision = "pending"
            else:
                overall_decision = "blocked"

        duration_ms = int((time.monotonic() - start) * 1000)

        logger.info(
            "ai_accountant_step4_policy",
            extra={
                "execution_id": execution_id,
                "overall_decision": overall_decision,
                "overall_confidence": overall_confidence,
                "violations": len(policy_violations),
                "significant_shifts": len(significant_shifts),
            },
        )
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

        logger.info(
            "ai_accountant_step5_db_writes_done",
            extra={"execution_id": execution_id, "wrote_results": overall_decision != "blocked"},
        )
        # STEP 6: Write Execution record
        # When called inline from the orchestrator, execution_id is provided — update that record.
        # When called as a standalone arq job, create a new record.
        if execution_id:
            resolved_execution_id = execution_id
        else:
            created = await db.execution.create(
                data={
                    "tenant_id": tenant_id,
                    "tool_id": tool_id,
                    "input_ref": json.dumps({"transaction_ids": transaction_ids, "trace_id": trace_id}),
                    "decision": overall_decision,
                    "confidence": overall_confidence,
                    "status": "completed",
                    "duration_ms": duration_ms,
                }
            )
            resolved_execution_id = created.id

        logger.info(
            "ai_accountant_step7_audit_start",
            extra={"execution_id": resolved_execution_id},
        )
        # STEP 7: Audit — append-only, must succeed or operation fails
        await write_audit_log(
            tenant_id=tenant_id,
            execution_id=resolved_execution_id,
            actor=f"tool:{tool_id}",
            action="ai_accountant:categorise_and_match",
            reasoning_trace={
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
                "category_distribution": dict(current_category_dist),
                "prior_period_category_distribution": dict(prior_category_dist),
                "category_shifts": significant_shifts,
                "has_significant_shifts": has_significant_shifts,
                "significant_shift_penalty": significant_shift_penalty_applied,
            },
            model_version=get_settings().claude_model,
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

        return ToolResult(
            execution_id=resolved_execution_id,
            decision=overall_decision,
            confidence=overall_confidence,
            results=results,
            reasoning_trace=reasoning_trace,
        )

    async def _call_claude(
        self,
        transactions: list,
        invoices: list,
        policy: _ToolPolicy,
        prior_category_dist: Counter[str] | None = None,
        tenant_id: str = "",
    ) -> tuple[list[TransactionResult], str]:
        settings = get_settings()
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        db = get_db()

        # Fetch recent manual corrections to use as few-shot examples (only if enabled in config)
        recent_corrections = await db.categorycorrection.find_many(
            where={"tenant_id": tenant_id},
            order={"created_at": "desc"},
            take=policy.max_correction_examples,
        ) if (tenant_id and policy.learn_from_corrections) else []

        correction_examples = ""
        if recent_corrections:
            examples = [
                f'  - "{c.merchant_name or c.description or "unknown"}" was corrected from "{c.original_category}" to "{c.corrected_category}"'
                for c in recent_corrections
            ]
            correction_examples = (
                "\nLEARNED CORRECTIONS (your team manually corrected these — apply the same logic):\n"
                + "\n".join(examples)
                + "\n"
            )

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

        drift_note = ""
        if prior_category_dist:
            current_dist: Counter[str] = Counter(
                t.get("plaid_category") for t in txn_list if t.get("plaid_category")
            )
            shifts_preview: list[dict] = []
            for cat, cur in current_dist.items():
                prior = prior_category_dist.get(cat, 0)
                if prior > 0:
                    change_pct = (cur - prior) / prior * 100
                    if abs(change_pct) > 50:
                        shifts_preview.append({
                            "category": cat,
                            "change_pct": round(change_pct, 1),
                            "current": cur,
                            "prior": prior,
                        })
            if shifts_preview:
                drift_note = (
                    f"\nNOTE: The following spend categories have shifted significantly "
                    f"vs the prior period: {json.dumps(shifts_preview)}. "
                    f"Flag any that seem anomalous in your reasoning.\n"
                )

        strict_coa_instruction = (
            "STRICT COA MODE: You MUST only use categories from the ALLOWED CATEGORIES list below. "
            "Do not invent new categories. If no category fits, use 'other'.\n"
            if policy.strict_coa_mode else
            "You should prefer categories from the ALLOWED CATEGORIES list, but may use 'other' for anything that does not fit.\n"
        )

        payroll_hint = ""
        if policy.payroll_keywords.strip():
            payroll_hint = (
                f"\nPAYROLL KEYWORDS: Transactions whose description or merchant name contains any of these "
                f"keywords must be categorised as 'payroll': {policy.payroll_keywords}\n"
            )

        prompt = f"""You are an AI accountant. Categorise each bank transaction and match it to an invoice if one exists.

TRANSACTIONS:
{json.dumps(txn_list, indent=2)}

OPEN INVOICES:
{json.dumps(invoice_list, indent=2)}

ALLOWED CATEGORIES: {", ".join(sorted(ALLOWED_CATEGORIES))}
{strict_coa_instruction}{payroll_hint}{drift_note}{correction_examples}
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
    tool_id: str,
    policy_config: dict | None = None,
) -> dict:
    """arq job wrapper for the AI Accountant Tool."""
    tool = AIAccountantTool()
    try:
        result = await tool.run(
            transaction_ids=transaction_ids,
            tenant_id=tenant_id,
            tool_id=tool_id,
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
