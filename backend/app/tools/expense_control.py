"""
Expense Control Tool — sub-agent tool. Called by Financial Orchestrator as a tool.
Validates expense claims against policy limits: monthly spend totals, per-transaction limits,
receipt requirements, and blocked categories. Claude categorises and flags violations.
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
from app.tools.base import BaseTool, ToolOutput, ToolType

logger = get_logger(__name__)

_ACTOR = "tool:expense_control:v1"
_MODEL_VERSION = "expense_control-v1"
_ACTION_RANK: dict[str, int] = {"approve": 0, "review": 1, "block": 2}


# -- Models ------------------------------------------------------------------


class _ToolPolicy(BaseModel):
    monthly_limit_per_employee: int = 100000  # pence
    receipt_required_above: int = 2500        # pence
    blocked_categories: list[str] = []
    per_transaction_limit: int = 50000                # minor units ($500)
    daily_spend_limit: int = 200000                   # minor units ($2,000)
    monthly_spend_limit: int = 500000                 # minor units ($5,000)
    pre_approval_required_above: int = 100000         # minor units ($1,000)
    blocked_mcc_allow_override: bool = False
    weekend_spend_enabled: bool = True
    international_spend_enabled: bool = True
    cash_advance_enabled: bool = False                # Primary fraud vector — off by default
    atm_withdrawal_enabled: bool = False
    meals_per_diem_limit: int = 10000                 # minor units ($100)
    hotel_daily_rate_limit: int = 35000               # minor units ($350)
    entertainment_monthly_limit: int = 25000          # minor units ($250)
    policy_violation_warning_count: int = 3
    policy_violation_suspend_count: int = 5


class _TransactionRecord(BaseModel):
    id: str
    tenant_id: str
    account_id: str
    amount_minor: int
    currency: str
    merchant_name: str | None
    description: str | None
    date: datetime
    category: str | None
    ai_category: str | None
    status: str


class _ClaudeTransactionResult(BaseModel):
    transaction_id: str
    category: str
    policy_violation: bool
    violation_reason: str | None
    action: Literal["approve", "review", "block"]
    reasoning: str


class _TransactionDecision(BaseModel):
    transaction_id: str
    category: str
    policy_violation: bool
    violation_reason: str | None
    action: Literal["approve", "review", "block"]
    reasoning: str
    hard_rule_applied: bool = False


def _parse_policy(config_json: dict) -> _ToolPolicy:
    raw = config_json.get("policy", config_json)
    return _ToolPolicy(
        monthly_limit_per_employee=raw.get("monthly_limit_per_employee", 100000),
        receipt_required_above=raw.get("receipt_required_above", 2500),
        blocked_categories=raw.get("blocked_categories", []),
        per_transaction_limit=raw.get("per_transaction_limit", 50000),
        daily_spend_limit=raw.get("daily_spend_limit", 200000),
        monthly_spend_limit=raw.get("monthly_spend_limit", 500000),
        pre_approval_required_above=raw.get("pre_approval_required_above", 100000),
        blocked_mcc_allow_override=raw.get("blocked_mcc_allow_override", False),
        weekend_spend_enabled=raw.get("weekend_spend_enabled", True),
        international_spend_enabled=raw.get("international_spend_enabled", True),
        cash_advance_enabled=raw.get("cash_advance_enabled", False),
        atm_withdrawal_enabled=raw.get("atm_withdrawal_enabled", False),
        meals_per_diem_limit=raw.get("meals_per_diem_limit", 10000),
        hotel_daily_rate_limit=raw.get("hotel_daily_rate_limit", 35000),
        entertainment_monthly_limit=raw.get("entertainment_monthly_limit", 25000),
        policy_violation_warning_count=raw.get("policy_violation_warning_count", 3),
        policy_violation_suspend_count=raw.get("policy_violation_suspend_count", 5),
    )



# -- Claude ------------------------------------------------------------------


def _build_claude_prompt(transactions: list[_TransactionRecord]) -> str:
    serialised = json.dumps(
        [
            {
                "transaction_id": t.id,
                "account_id": t.account_id,
                "amount_minor": t.amount_minor,
                "currency": t.currency,
                "merchant_name": t.merchant_name,
                "description": t.description,
                "date": t.date.isoformat(),
                "category": t.category,
                "ai_category": t.ai_category,
            }
            for t in transactions
        ],
        indent=2,
    )
    return (
        "You are an expense policy compliance model. Review each transaction and return a JSON array "
        "— one object per transaction — with fields: transaction_id (string), category (string), "
        "policy_violation (bool), violation_reason (string|null), "
        'action ("approve"|"review"|"block"), reasoning (string).\n'
        "Rules: clear violation → block; ambiguous → review; normal business expense → approve.\n"
        "Return ONLY a valid JSON array. No markdown, no prose.\n\n"
        f"Transactions:\n{serialised}"
    )


async def _call_claude(
    transactions: list[_TransactionRecord],
    settings_obj,
) -> list[_ClaudeTransactionResult]:
    client = AsyncAnthropic(api_key=settings_obj.anthropic_api_key)
    prompt = _build_claude_prompt(transactions)
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
            return [_ClaudeTransactionResult(**item) for item in parsed]
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

    raise RuntimeError(f"Claude API failed after {settings_obj.max_agent_attempts} attempts: {last_exc}")


# -- Core execution ----------------------------------------------------------


async def _execute_expense_control(
    tenant_id: str,
    tool_id: str,
    execution_id: str,
    transaction_ids: list[str],
) -> dict:
    settings_obj = get_settings()
    db = get_db()

    # Fetch tool config scoped to tenant
    tool = await db.tool.find_first(
        where={"id": tool_id, "tenant_id": tenant_id}
    )
    if tool is None:
        raise ValueError(f"Tool {tool_id} not found for tenant {tenant_id}")

    config_raw: dict = tool.config_json if isinstance(tool.config_json, dict) else {}
    policy = _parse_policy(config_raw)

    # Fetch transactions scoped to tenant
    raw_txns = await db.banktransaction.find_many(
        where={"id": {"in": transaction_ids}, "tenant_id": tenant_id}
    )
    if not raw_txns:
        raise ValueError("No transactions found for supplied IDs within this tenant")

    transactions = [_TransactionRecord(**{f: getattr(t, f) for f in _TransactionRecord.model_fields}) for t in raw_txns]

    blocked_categories_lower = [c.lower() for c in policy.blocked_categories]

    # Hard rules FIRST — applied before Claude
    hard_rule_decisions: dict[str, _TransactionDecision] = {}
    claude_candidates: list[_TransactionRecord] = []

    for txn in transactions:
        effective_category = (txn.ai_category or txn.category or "").lower()

        # Block: single transaction over monthly limit
        if txn.amount_minor > policy.monthly_limit_per_employee:
            hard_rule_decisions[txn.id] = _TransactionDecision(
                transaction_id=txn.id,
                category=effective_category or "unknown",
                policy_violation=True,
                violation_reason=(
                    f"Transaction amount {txn.amount_minor} exceeds monthly limit "
                    f"{policy.monthly_limit_per_employee}"
                ),
                action="block",
                reasoning="Single transaction exceeds the configured monthly per-employee limit.",
                hard_rule_applied=True,
            )
            continue

        # Block: category in blocked list (case-insensitive)
        if effective_category and effective_category in blocked_categories_lower:
            hard_rule_decisions[txn.id] = _TransactionDecision(
                transaction_id=txn.id,
                category=effective_category,
                policy_violation=True,
                violation_reason=f"Category '{effective_category}' is blocked by policy.",
                action="block",
                reasoning="Transaction category is on the blocked-categories list.",
                hard_rule_applied=True,
            )
            continue

        claude_candidates.append(txn)

    # Call Claude on remaining transactions
    claude_map: dict[str, _ClaudeTransactionResult] = {}
    if claude_candidates:
        claude_results = await _call_claude(claude_candidates, settings_obj)
        claude_map = {r.transaction_id: r for r in claude_results}

    # Merge: hard rules take precedence, then Claude candidates
    decisions: list[_TransactionDecision] = list(hard_rule_decisions.values())

    for txn in claude_candidates:
        claude_result = claude_map.get(txn.id)

        if claude_result is None:
            decisions.append(_TransactionDecision(
                transaction_id=txn.id, category="unknown", policy_violation=True,
                violation_reason="Claude did not return a result for this transaction.",
                action="review", reasoning="Missing Claude categorisation — flagged for manual review.",
                hard_rule_applied=False,
            ))
            continue

        action: Literal["approve", "review", "block"] = claude_result.action

        # Receipt required check — escalate to review if not already blocked
        if txn.amount_minor > policy.receipt_required_above and action == "approve":
            action = "review"
            violation_reason = (
                f"Amount {txn.amount_minor} exceeds receipt threshold "
                f"{policy.receipt_required_above} — receipt required."
            )
        else:
            violation_reason = claude_result.violation_reason

        decisions.append(
            _TransactionDecision(
                transaction_id=txn.id,
                category=claude_result.category,
                policy_violation=claude_result.policy_violation,
                violation_reason=violation_reason,
                action=action,
                reasoning=claude_result.reasoning,
                hard_rule_applied=False,
            )
        )

    # Monthly total for tenant (calendar month so far)
    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_txns = await db.banktransaction.find_many(
        where={
            "tenant_id": tenant_id,
            "date": {"gte": month_start},
        }
    )
    monthly_total: int = sum(t.amount_minor for t in monthly_txns)

    # If monthly total exceeds limit, escalate remaining approved transactions to review
    if monthly_total > policy.monthly_limit_per_employee:
        for decision in decisions:
            if decision.action == "approve":
                decision.action = "review"
                decision.policy_violation = True
                decision.violation_reason = (
                    f"Monthly spend total {monthly_total} exceeds limit "
                    f"{policy.monthly_limit_per_employee} — flagged for review."
                )

    # Derive overall decision
    has_block = any(d.action == "block" for d in decisions)
    has_review = any(d.action == "review" for d in decisions)

    if has_block:
        overall_decision = "blocked"
    elif has_review:
        overall_decision = "approval_required"
    else:
        overall_decision = "auto_approved"

    violation_count = sum(1 for d in decisions if d.policy_violation)
    confidence = round(
        1.0 - (violation_count / len(decisions)) if overall_decision == "auto_approved"
        else violation_count / len(decisions),
        4,
    )

    # Build reasoning trace
    reasoning_trace: dict = {
        "overall_decision": overall_decision,
        "transaction_count": len(decisions),
        "monthly_total_minor": monthly_total,
        "monthly_limit_minor": policy.monthly_limit_per_employee,
        "policy": policy.model_dump(),
        "per_transaction": [
            {
                "transaction_id": d.transaction_id,
                "category": d.category,
                "policy_violation": d.policy_violation,
                "violation_reason": d.violation_reason,
                "action": d.action,
                "reasoning": d.reasoning,
                "hard_rule_applied": d.hard_rule_applied,
            }
            for d in decisions
        ],
    }

    # Audit log BEFORE any DB update — operation fails if audit fails
    await write_audit_log(
        tenant_id=tenant_id,
        actor=_ACTOR,
        action=f"expense_control:{overall_decision}",
        reasoning_trace=reasoning_trace,
        model_version=_MODEL_VERSION,
        execution_id=execution_id,
    )

    # Update transaction statuses in DB
    review_ids = [d.transaction_id for d in decisions if d.action == "review"]
    block_ids = [d.transaction_id for d in decisions if d.action == "block"]

    if block_ids:
        await db.banktransaction.update_many(
            where={"id": {"in": block_ids}, "tenant_id": tenant_id},
            data={"status": "blocked"},
        )
    if review_ids:
        await db.banktransaction.update_many(
            where={"id": {"in": review_ids}, "tenant_id": tenant_id},
            data={"status": "flagged"},
        )

    actions_taken: list[str] = []
    if block_ids:
        actions_taken.append(f"blocked {len(block_ids)} transaction(s)")
    if review_ids:
        actions_taken.append(f"flagged {len(review_ids)} transaction(s) for review")
    if not block_ids and not review_ids:
        actions_taken.append("all transactions approved — no status change")

    return {
        "decision": overall_decision,
        "confidence": confidence,
        "reasoning": json.dumps(reasoning_trace),
        "actions_taken": actions_taken,
        "output_data": reasoning_trace,
    }


# -- arq job -----------------------------------------------------------------


async def run_expense_control_job(
    ctx: dict,
    *,
    execution_id: str,
    tenant_id: str,
    tool_id: str,
    transaction_ids: list[str],
) -> dict:
    db = get_db()
    settings_obj = get_settings()
    start_ms = int(time.time() * 1000)

    try:
        result = await _execute_expense_control(
            tenant_id, tool_id, execution_id, transaction_ids
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
                function_name="run_expense_control_job",
                error=str(exc),
            )
        raise


# -- BaseTool --------------------------------------------------------------


class ExpenseControlTool(BaseTool):
    TOOL_TYPE = ToolType.EXPENSE_CONTROL
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> ToolOutput:
        execution_id: str = input_data["execution_id"]
        tool_id: str = input_data["tool_id"]
        transaction_ids: list[str] = input_data["transaction_ids"]

        result = await _execute_expense_control(
            tenant_id, tool_id, execution_id, transaction_ids
        )
        return ToolOutput(
            tool_type=self.TOOL_TYPE,
            decision=result["decision"],
            confidence=result["confidence"],
            reasoning=result["reasoning"],
            actions_taken=result["actions_taken"],
            output_data=result["output_data"],
        )
