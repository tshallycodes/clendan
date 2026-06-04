"""
AI Accountant Worker — categorises bank transactions and matches them to invoices.
Sub-agent called by the Financial Orchestrator as a tool.
Follows mandatory execution flow: receive → classify → execute → policy check → output → audit.
"""
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any

import anthropic

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger, get_trace_id

logger = get_logger(__name__)

MODEL = "claude-sonnet-4-6"

ALLOWED_CATEGORIES = {
    "advertising", "bank_fees", "consulting", "equipment", "insurance",
    "legal", "meals", "office_supplies", "payroll", "rent", "software",
    "tax", "travel", "utilities", "other",
}

AUTO_CONFIDENCE_THRESHOLD = 0.85
APPROVE_CONFIDENCE_THRESHOLD = 0.50


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
    model_version: str = MODEL


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
    ) -> WorkerResult:
        start = time.monotonic()
        trace_id = get_trace_id()
        db = get_db()

        # STEP 1: Receive + validate input
        if not transaction_ids:
            raise ValueError("transaction_ids cannot be empty")
        if not tenant_id:
            raise ValueError("tenant_id required")

        # STEP 2: Classify — fetch transactions scoped to tenant
        transactions = await db.banktransaction.find_many(
            where={"id": {"in": transaction_ids}, "tenant_id": tenant_id}
        )
        if not transactions:
            raise ValueError("No transactions found for tenant")

        # Fetch existing invoices for matching context
        invoices = await db.invoice.find_many(
            where={"tenant_id": tenant_id, "status": {"in": ["pending", "approved"]}},
            take=50,
            order={"created_at": "desc"},
        )

        # STEP 3: Execute — call Claude
        results, reasoning_trace = await self._call_claude(transactions, invoices, tenant_id)

        # STEP 4: Policy check — validate every result
        policy_violations = []
        for r in results:
            if r.ai_category not in ALLOWED_CATEGORIES:
                policy_violations.append(f"Invalid category '{r.ai_category}' for txn {r.transaction_id}")
            if not (0.0 <= r.confidence <= 1.0):
                policy_violations.append(f"Confidence out of range for txn {r.transaction_id}")

        if policy_violations:
            logger.warning("Policy violations in AI Accountant output: %s", policy_violations)
            overall_decision = "blocked"
            overall_confidence = 0.0
        else:
            confidences = [r.confidence for r in results]
            overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            if overall_confidence >= AUTO_CONFIDENCE_THRESHOLD:
                overall_decision = "auto"
            elif overall_confidence >= APPROVE_CONFIDENCE_THRESHOLD:
                overall_decision = "pending"
            else:
                overall_decision = "blocked"

        duration_ms = int((time.monotonic() - start) * 1000)

        # STEP 5: Output — write results to DB (only if not blocked)
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
                "status": overall_decision,
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
                "model_version": MODEL,
            }
        )

        logger.info(
            "AI Accountant: tenant=%s txns=%d decision=%s confidence=%.2f duration_ms=%d",
            tenant_id, len(results), overall_decision, overall_confidence, duration_ms,
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
        tenant_id: str,
    ) -> tuple[list[TransactionResult], str]:
        settings = get_settings()
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

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

        message = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Claude returned non-JSON output for AI Accountant")
            raise ValueError("Claude returned non-JSON — cannot parse categorisation results")

        results = []
        for item in parsed:
            category = item.get("ai_category", "other").lower().strip()
            if category not in ALLOWED_CATEGORIES:
                category = "other"
            confidence = float(item.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))

            if confidence >= AUTO_CONFIDENCE_THRESHOLD:
                decision = "auto"
            elif confidence >= APPROVE_CONFIDENCE_THRESHOLD:
                decision = "pending"
            else:
                decision = "blocked"

            results.append(TransactionResult(
                transaction_id=item.get("transaction_id", ""),
                ai_category=category,
                matched_invoice_id=item.get("matched_invoice_id"),
                confidence=confidence,
                reasoning=item.get("reasoning", ""),
                decision=decision,
            ))

        return results, raw


async def run_ai_accountant(ctx: dict, transaction_ids: list[str], tenant_id: str, worker_id: str) -> dict:
    """arq job wrapper for the AI Accountant Worker."""
    worker = AIAccountantWorker()
    result = await worker.run(
        transaction_ids=transaction_ids,
        tenant_id=tenant_id,
        worker_id=worker_id,
    )
    return {
        "execution_id": result.execution_id,
        "decision": result.decision,
        "confidence": result.confidence,
        "transactions_processed": len(result.results),
    }
