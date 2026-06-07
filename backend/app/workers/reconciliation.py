"""
Reconciliation Worker — sub-agent worker. Called by Financial Orchestrator as a tool.
Matches bank transactions against invoices. Detects unmatched items and uses Claude
to assess severity. Decides: matched / review_required / flagged per unmatched item,
then derives an overall execution decision.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime, timedelta
from typing import Literal

from anthropic import APIConnectionError, APIStatusError, AsyncAnthropic
from pydantic import BaseModel

from app.audit.logger import write_audit_log
from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.queue.pool import push_to_dlq
from app.workers.base import BaseWorker, WorkerOutput, WorkerType

logger = get_logger(__name__)

_ACTOR = "worker:reconciliation:v1"
_MODEL_VERSION = "reconciliation-v1"


# ---------------------------------------------------------------------------
# Internal data models
# ---------------------------------------------------------------------------


class _WorkerPolicy(BaseModel):
    amount_tolerance_pence: int = 100
    staleness_days: int = 30
    auto_match_confidence_min: float = 0.95
    amount_tolerance_minor_units: int = 150      # $1.50 — Numeric guide
    amount_tolerance_pct: float = 0.0003         # 0.03%
    date_tolerance_days: int = 5
    partial_match_enabled: bool = True
    partial_match_max_lines: int = 20
    reconciliation_frequency: str = "daily"      # "real_time" | "daily" | "weekly"
    unmatched_alert_days: int = 5
    forex_tolerance_pct: float = 0.02
    intercompany_auto_eliminate: bool = False
    stale_open_item_days: int = 90
    period_lock_respect: bool = True
    segregation_of_duties_enforced: bool = True


class _TransactionRecord(BaseModel):
    id: str
    tenant_id: str
    account_id: str
    amount_minor: int
    currency: str
    merchant_name: str | None
    description: str | None
    date: datetime
    status: str


class _InvoiceRecord(BaseModel):
    id: str
    tenant_id: str
    vendor: str | None
    invoice_number: str | None
    amount_minor: int
    currency: str
    due_date: datetime | None
    status: str
    created_at: datetime


class _ClaudeItemResult(BaseModel):
    item_id: str
    item_type: Literal["transaction", "invoice"]
    severity: Literal["low", "medium", "high"]
    action: Literal["ok", "review", "flag"]
    reasoning: str


# ---------------------------------------------------------------------------
# Policy helper
# ---------------------------------------------------------------------------


def _parse_policy(config_json: dict) -> _WorkerPolicy:
    raw = config_json.get("policy", config_json)
    return _WorkerPolicy(
        amount_tolerance_pence=raw.get("amount_tolerance_pence", 100),
        staleness_days=raw.get("staleness_days", 30),
        auto_match_confidence_min=raw.get("auto_match_confidence_min", 0.95),
        amount_tolerance_minor_units=raw.get("amount_tolerance_minor_units", 150),
        amount_tolerance_pct=raw.get("amount_tolerance_pct", 0.0003),
        date_tolerance_days=raw.get("date_tolerance_days", 5),
        partial_match_enabled=raw.get("partial_match_enabled", True),
        partial_match_max_lines=raw.get("partial_match_max_lines", 20),
        reconciliation_frequency=raw.get("reconciliation_frequency", "daily"),
        unmatched_alert_days=raw.get("unmatched_alert_days", 5),
        forex_tolerance_pct=raw.get("forex_tolerance_pct", 0.02),
        intercompany_auto_eliminate=raw.get("intercompany_auto_eliminate", False),
        stale_open_item_days=raw.get("stale_open_item_days", 90),
        period_lock_respect=raw.get("period_lock_respect", True),
        segregation_of_duties_enforced=raw.get("segregation_of_duties_enforced", True),
    )


# ---------------------------------------------------------------------------
# Claude assessment
# ---------------------------------------------------------------------------


def _build_claude_prompt(
    unmatched_transactions: list[dict],
    unmatched_invoices: list[dict],
) -> str:
    payload = json.dumps(
        {
            "unmatched_transactions": unmatched_transactions,
            "unmatched_invoices": unmatched_invoices,
        },
        indent=2,
        default=str,
    )
    return (
        "You are a financial reconciliation model. Assess each unmatched item below and return "
        "a JSON array — one object per item — with exactly these fields:\n"
        '  "item_id": string (copy from input),\n'
        '  "item_type": "transaction" or "invoice",\n'
        '  "severity": "low" | "medium" | "high",\n'
        '  "action": "ok" | "review" | "flag",\n'
        '  "reasoning": one concise sentence explaining the assessment.\n\n'
        "Severity guidance:\n"
        "- high: large amounts, stale items, duplicate-looking entries, or suspicious patterns\n"
        "- medium: moderate amounts unmatched for a reasonable time\n"
        "- low: small amounts or recently created items\n\n"
        "Action guidance:\n"
        "- flag: high severity items requiring immediate attention\n"
        "- review: medium severity items requiring human review\n"
        "- ok: low severity items that can be auto-resolved\n\n"
        "Return ONLY a valid JSON array. No markdown, no prose.\n\n"
        f"Unmatched items:\n{payload}"
    )


async def _call_claude(
    unmatched_txns: list[_TransactionRecord],
    unmatched_invs: list[_InvoiceRecord],
    settings_obj,
) -> list[_ClaudeItemResult]:
    client = AsyncAnthropic(api_key=settings_obj.anthropic_api_key)

    txn_dicts = [
        {
            "item_id": t.id,
            "item_type": "transaction",
            "amount_minor": t.amount_minor,
            "currency": t.currency,
            "merchant_name": t.merchant_name,
            "description": t.description,
            "date": t.date.isoformat(),
            "status": t.status,
        }
        for t in unmatched_txns
    ]
    inv_dicts = [
        {
            "item_id": i.id,
            "item_type": "invoice",
            "amount_minor": i.amount_minor,
            "currency": i.currency,
            "vendor": i.vendor,
            "invoice_number": i.invoice_number,
            "due_date": i.due_date.isoformat() if i.due_date else None,
            "created_at": i.created_at.isoformat(),
            "status": i.status,
        }
        for i in unmatched_invs
    ]

    prompt = _build_claude_prompt(txn_dicts, inv_dicts)
    last_exc: Exception | None = None

    for attempt in range(settings_obj.max_agent_attempts):
        try:
            message = await client.messages.create(
                model=settings_obj.claude_model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = message.content[0].text.strip()
            parsed = json.loads(raw_text)
            if not isinstance(parsed, list):
                raise ValueError("Claude response is not a JSON array")
            return [_ClaudeItemResult(**item) for item in parsed]
        except (APIStatusError, APIConnectionError) as exc:
            last_exc = exc
            logger.error(
                "claude_api_error",
                extra={"attempt": attempt + 1, "error": str(exc)},
            )
            if attempt < settings_obj.max_agent_attempts - 1:
                await asyncio.sleep(settings_obj.backoff_seconds * (attempt + 1))
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            raise RuntimeError(f"Claude returned unparseable response: {exc}") from exc

    raise RuntimeError(
        f"Claude API failed after {settings_obj.max_agent_attempts} attempts: {last_exc}"
    )


# ---------------------------------------------------------------------------
# Core execution
# ---------------------------------------------------------------------------


async def _execute_reconciliation(
    tenant_id: str,
    worker_id: str,
    execution_id: str,
    period_days: int = 30,
) -> dict:
    settings_obj = get_settings()
    db = get_db()

    # Fetch worker config scoped to tenant
    worker = await db.worker.find_first(
        where={"id": worker_id, "tenant_id": tenant_id}
    )
    if worker is None:
        raise ValueError(f"Worker {worker_id} not found for tenant {tenant_id}")

    config_raw: dict = worker.config_json if isinstance(worker.config_json, dict) else {}
    policy = _parse_policy(config_raw)

    cutoff = datetime.now(UTC) - timedelta(days=period_days)
    staleness_cutoff = datetime.now(UTC) - timedelta(days=policy.staleness_days)

    # Fetch pending bank transactions scoped to tenant
    raw_txns = await db.banktransaction.find_many(
        where={
            "tenant_id": tenant_id,
            "status": "pending",
            "date": {"gte": cutoff},
        }
    )
    transactions = [
        _TransactionRecord(
            id=t.id,
            tenant_id=t.tenant_id,
            account_id=t.account_id,
            amount_minor=t.amount_minor,
            currency=t.currency,
            merchant_name=t.merchant_name,
            description=t.description,
            date=t.date,
            status=t.status,
        )
        for t in raw_txns
    ]

    # Fetch pending invoices scoped to tenant
    raw_invs = await db.invoice.find_many(
        where={
            "tenant_id": tenant_id,
            "status": "pending",
            "created_at": {"gte": cutoff},
        }
    )
    invoices = [
        _InvoiceRecord(
            id=i.id,
            tenant_id=i.tenant_id,
            vendor=i.vendor,
            invoice_number=i.invoice_number,
            amount_minor=i.amount_minor,
            currency=i.currency,
            due_date=i.due_date,
            status=i.status,
            created_at=i.created_at,
        )
        for i in raw_invs
    ]

    # Amount-based matching — integer arithmetic only, no floats for currency
    matched_txn_ids: set[str] = set()
    matched_inv_ids: set[str] = set()

    for invoice in invoices:
        for txn in transactions:
            if txn.id in matched_txn_ids:
                continue
            if abs(txn.amount_minor - invoice.amount_minor) <= policy.amount_tolerance_pence:
                matched_txn_ids.add(txn.id)
                matched_inv_ids.add(invoice.id)
                break

    unmatched_txns = [t for t in transactions if t.id not in matched_txn_ids]
    unmatched_invs = [i for i in invoices if i.id not in matched_inv_ids]

    # Identify stale unmatched items
    stale_txn_ids: set[str] = {t.id for t in unmatched_txns if t.date < staleness_cutoff}
    stale_inv_ids: set[str] = {
        i.id for i in unmatched_invs if i.created_at < staleness_cutoff
    }

    # Call Claude only when there are unmatched items
    claude_results: list[_ClaudeItemResult] = []
    if unmatched_txns or unmatched_invs:
        claude_results = await _call_claude(unmatched_txns, unmatched_invs, settings_obj)

    # Derive overall decision
    has_flag = any(r.action == "flag" for r in claude_results)
    has_review = any(r.action == "review" for r in claude_results)

    if has_flag:
        overall_decision = "flagged"
    elif has_review:
        overall_decision = "approval_required"
    else:
        overall_decision = "auto_approved"

    total_items = len(transactions) + len(invoices)
    matched_count = len(matched_txn_ids) + len(matched_inv_ids)
    confidence = round(matched_count / total_items, 4) if total_items > 0 else 1.0

    reasoning_trace: dict = {
        "overall_decision": overall_decision,
        "period_days": period_days,
        "policy": policy.model_dump(),
        "transaction_count": len(transactions),
        "invoice_count": len(invoices),
        "matched_transactions": len(matched_txn_ids),
        "matched_invoices": len(matched_inv_ids),
        "unmatched_transactions": len(unmatched_txns),
        "unmatched_invoices": len(unmatched_invs),
        "stale_transaction_ids": list(stale_txn_ids),
        "stale_invoice_ids": list(stale_inv_ids),
        "claude_assessments": [r.model_dump() for r in claude_results],
    }

    # Audit log BEFORE any DB updates — operation fails if audit fails
    await write_audit_log(
        tenant_id=tenant_id,
        actor=_ACTOR,
        action=f"reconciliation:{overall_decision}",
        reasoning_trace=reasoning_trace,
        model_version=_MODEL_VERSION,
        execution_id=execution_id,
    )

    # Update matched records in DB
    if matched_txn_ids:
        await db.banktransaction.update_many(
            where={"id": {"in": list(matched_txn_ids)}, "tenant_id": tenant_id},
            data={"status": "matched"},
        )
    if matched_inv_ids:
        await db.invoice.update_many(
            where={"id": {"in": list(matched_inv_ids)}, "tenant_id": tenant_id},
            data={"status": "matched"},
        )

    actions_taken: list[str] = []
    if matched_txn_ids:
        actions_taken.append(f"matched {len(matched_txn_ids)} transaction(s)")
    if matched_inv_ids:
        actions_taken.append(f"matched {len(matched_inv_ids)} invoice(s)")
    if unmatched_txns:
        actions_taken.append(f"{len(unmatched_txns)} transaction(s) unmatched — pending review")
    if unmatched_invs:
        actions_taken.append(f"{len(unmatched_invs)} invoice(s) unmatched — pending review")
    if not actions_taken:
        actions_taken.append("no pending items found — nothing to reconcile")

    return {
        "decision": overall_decision,
        "confidence": confidence,
        "reasoning": json.dumps(reasoning_trace),
        "actions_taken": actions_taken,
        "output_data": reasoning_trace,
    }


# ---------------------------------------------------------------------------
# arq job entrypoint
# ---------------------------------------------------------------------------


async def run_reconciliation_job(
    ctx: dict,
    *,
    execution_id: str,
    tenant_id: str,
    worker_id: str,
    period_days: int = 30,
) -> dict:
    db = get_db()
    settings_obj = get_settings()
    start_ms = int(time.time() * 1000)

    try:
        result = await _execute_reconciliation(
            tenant_id, worker_id, execution_id, period_days
        )
        duration_ms = int(time.time() * 1000) - start_ms
        await db.execution.update(
            where={"id": execution_id},
            data={
                "status": "completed",
                "decision": result["decision"],
                "confidence": result["confidence"],
                "duration_ms": duration_ms,
            },
        )
        if result["decision"] == "approval_required":
            await db.approval.create(
                data={
                    "tenant_id": tenant_id,
                    "execution_id": execution_id,
                    "expires_at": datetime.now(UTC)
                    + timedelta(seconds=settings_obj.approval_ttl_seconds),
                }
            )
        return result
    except Exception as exc:
        try:
            await db.execution.update(
                where={"id": execution_id},
                data={"status": "failed", "decision": "failed"},
            )
        except Exception:
            pass
        if ctx.get("job_try", 1) >= 3:
            await push_to_dlq(
                job_id=str(ctx.get("job_id", "unknown")),
                function_name="run_reconciliation_job",
                error=str(exc),
            )
        raise


# ---------------------------------------------------------------------------
# BaseWorker class (orchestrator interface)
# ---------------------------------------------------------------------------


class ReconciliationWorker(BaseWorker):
    WORKER_TYPE = WorkerType.RECONCILIATION
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> WorkerOutput:
        execution_id: str = input_data["execution_id"]
        worker_id: str = input_data["worker_id"]
        period_days: int = input_data.get("period_days", 30)

        result = await _execute_reconciliation(
            tenant_id, worker_id, execution_id, period_days
        )
        return WorkerOutput(
            worker_type=self.WORKER_TYPE,
            decision=result["decision"],
            confidence=result["confidence"],
            reasoning=result["reasoning"],
            actions_taken=result["actions_taken"],
            output_data=result["output_data"],
        )
