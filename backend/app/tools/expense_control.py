"""Expense Control Tool — validates AccountingExpense records against policy limits.
Uses AccountingAccount (chart of accounts) to detect miscategorized spend.
Claude summarises spend by category and recommends approve | flag | block per expense."""
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
_ACTION_RANK: dict[str, int] = {"approve": 0, "flag": 1, "block": 2}

# Round-number check: multiples of $100 (10 000 cents) above $500 (50 000 cents)
_ROUND_NUMBER_MODULUS: int = 10_000
_ROUND_NUMBER_MIN_CENTS: int = 50_000


class _ToolPolicy(BaseModel):
    single_expense_limit_cents: int = 100_000       # $1 000
    approval_required_cents: int = 50_000           # $500
    auto_approve_limit_cents: int = 10_000          # $100
    allowed_categories: list[str] = []
    # Retained fields used by existing stored configs
    monthly_limit_per_employee: int = 500_000
    blocked_categories: list[str] = []
    receipt_required_above: int = 2_500
    lookback_days: int = 30


class _ExpenseRecord(BaseModel):
    id: str
    tenant_id: str
    amount_cents: int
    category: str | None
    account_code: str | None
    approved: bool
    expense_date: datetime | None
    contact_name: str | None


class _AccountRecord(BaseModel):
    id: str
    code: str
    name: str
    account_type: str


class _ClaudeExpenseResult(BaseModel):
    expense_id: str
    recommended_action: Literal["approve", "flag", "block"]
    reasoning: str
    spend_category_summary: str | None = None
    burn_rate_assessment: str | None = None


class _ExpenseDecision(BaseModel):
    expense_id: str
    amount_cents: int
    category: str | None
    account_code: str | None
    flags: list[str]
    action: Literal["approve", "flag", "block"]
    reasoning: str
    hard_rule_applied: bool = False


def _parse_policy(config_json: dict) -> _ToolPolicy:
    raw = config_json.get("policy", config_json)
    return _ToolPolicy.model_validate({k: v for k, v in raw.items() if k in _ToolPolicy.model_fields})


def _apply_hard_rules(
    expense: _ExpenseRecord,
    valid_account_codes: set[str],
    policy: _ToolPolicy,
) -> tuple[list[str], Literal["approve", "flag", "block"] | None]:
    """Returns (flags, action) where action is None if no hard rule fired."""
    flags: list[str] = []
    worst: Literal["approve", "flag", "block"] = "approve"

    def _up(a: Literal["approve", "flag", "block"]) -> None:
        nonlocal worst
        if _ACTION_RANK[a] > _ACTION_RANK[worst]:
            worst = a

    if expense.amount_cents > policy.single_expense_limit_cents:
        flags.append(f"amount {expense.amount_cents} exceeds limit {policy.single_expense_limit_cents}")
        _up("block")
    if not expense.approved and expense.amount_cents > policy.approval_required_cents:
        flags.append(f"unapproved: {expense.amount_cents} exceeds approval_required_cents {policy.approval_required_cents}")
        _up("flag")
    if expense.account_code and valid_account_codes and expense.account_code not in valid_account_codes:
        flags.append(f"account_code '{expense.account_code}' not in chart of accounts — miscategorized")
        _up("flag")
    if expense.amount_cents >= _ROUND_NUMBER_MIN_CENTS and expense.amount_cents % _ROUND_NUMBER_MODULUS == 0:
        flags.append(f"suspicious round number: {expense.amount_cents}")
        _up("flag")

    return (flags, worst) if flags else (flags, None)


async def _call_claude(
    expenses: list[_ExpenseRecord],
    valid_accounts: list[_AccountRecord],
    policy: _ToolPolicy,
    settings_obj,
    daily_burn_minor: int = 0,
    projected_month_spend_minor: int = 0,
) -> list[_ClaudeExpenseResult]:
    client = AsyncAnthropic(api_key=settings_obj.anthropic_api_key)
    data = json.dumps({
        "expenses": [
            {"expense_id": e.id, "amount_cents": e.amount_cents, "category": e.category,
             "account_code": e.account_code, "approved": e.approved,
             "expense_date": e.expense_date.isoformat() if e.expense_date else None,
             "contact_name": e.contact_name}
            for e in expenses
        ],
        "valid_chart_of_accounts": [
            {"code": a.code, "name": a.name, "account_type": a.account_type}
            for a in valid_accounts
        ],
        "policy": {
            "single_expense_limit_cents": policy.single_expense_limit_cents,
            "approval_required_cents": policy.approval_required_cents,
            "auto_approve_limit_cents": policy.auto_approve_limit_cents,
            "allowed_categories": policy.allowed_categories,
            "blocked_categories": policy.blocked_categories,
        },
        "burn_rate_context": {"daily_burn_minor": daily_burn_minor,
            "projected_month_spend_minor": projected_month_spend_minor,
            "period_days": policy.lookback_days},
    }, indent=2)
    prompt = (
        "You are an expense compliance model. Review expenses against the policy and chart of accounts. "
        "Return a JSON array — one object per expense — with fields: "
        '"expense_id" (string), "recommended_action" ("approve"|"flag"|"block"), '
        '"reasoning" (one sentence), "spend_category_summary" (brief spend summary on first item only, null elsewhere), '
        '"burn_rate_assessment" (string on first item only: is the current spending velocity sustainable? '
        "any spending patterns that suggest budget overrun risk? null on all other items). "
        "block=clear violation; flag=unapproved/ambiguous/suspicious; approve=legitimate within policy. "
        f"NEVER approve amounts above {policy.auto_approve_limit_cents} without explicit approval. "
        f"Return ONLY a valid JSON array.\n\nData:\n{data}"
    )
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
            return [_ClaudeExpenseResult(**item) for item in parsed]
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


async def _execute_expense_control(
    tenant_id: str,
    tool_id: str,
    execution_id: str,
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

    # 1. Fetch AccountingExpense records for tenant, last 30 days
    cutoff = datetime.now(UTC) - timedelta(days=30)
    raw_expenses = await db.accountingexpense.find_many(
        where={
            "tenant_id": tenant_id,
            "expense_date": {"gte": cutoff},
        }
    )
    if not raw_expenses:
        # Nothing to process — write audit and return
        reasoning_trace: dict = {
            "overall_decision": "auto_approved",
            "expense_count": 0,
            "note": "no expenses in last 30 days",
            "policy": policy.model_dump(),
        }
        await write_audit_log(
            tenant_id=tenant_id,
            actor=_ACTOR,
            action="expense_control:auto_approved",
            reasoning_trace=reasoning_trace,
            model_version=_MODEL_VERSION,
            execution_id=execution_id,
        )
        return {
            "decision": "auto_approved",
            "confidence": 1.0,
            "reasoning": json.dumps(reasoning_trace),
            "actions_taken": ["no expenses found in last 30 days — nothing to process"],
            "output_data": reasoning_trace,
        }

    expenses = [
        _ExpenseRecord(id=e.id, tenant_id=e.tenant_id, amount_cents=e.amount_cents,
            category=e.category, account_code=e.account_code, approved=e.approved,
            expense_date=e.expense_date, contact_name=e.contact_name)
        for e in raw_expenses
    ]

    # 1b. Period utilization — compute burn rate from fetched expenses
    period_days: int = policy.lookback_days
    if period_days > 0 and expenses:
        total_spend = sum(e.amount_cents for e in expenses)
        daily_burn_minor: int = total_spend // max(period_days, 1)
        projected_month_spend_minor: int = daily_burn_minor * 30
    else:
        daily_burn_minor = 0
        projected_month_spend_minor = 0

    # Period-adjusted threshold: flag high burn rate (burning 10x auto-approve limit per day)
    high_burn_rate: bool = daily_burn_minor > policy.auto_approve_limit_cents * 10

    # 2. Fetch EXPENSE-type accounts from chart of accounts
    raw_accounts = await db.accountingaccount.find_many(
        where={"tenant_id": tenant_id, "account_type": "EXPENSE"}
    )
    valid_accounts = [
        _AccountRecord(id=a.id, code=a.code, name=a.name, account_type=a.account_type)
        for a in raw_accounts
    ]
    valid_account_codes: set[str] = {a.code for a in valid_accounts}

    # 3. Apply hard rules per expense
    hard_rule_decisions: dict[str, _ExpenseDecision] = {}
    claude_candidates: list[_ExpenseRecord] = []

    for expense in expenses:
        flags, hard_action = _apply_hard_rules(expense, valid_account_codes, policy)
        if hard_action is not None:
            hard_rule_decisions[expense.id] = _ExpenseDecision(
                expense_id=expense.id,
                amount_cents=expense.amount_cents,
                category=expense.category,
                account_code=expense.account_code,
                flags=flags,
                action=hard_action,
                reasoning="; ".join(flags),
                hard_rule_applied=True,
            )
        else:
            claude_candidates.append(expense)

    # 4. Ask Claude to review remaining expenses + summarize spend by category
    claude_map: dict[str, _ClaudeExpenseResult] = {}
    spend_summary: str | None = None
    burn_rate_assessment: str | None = None
    if claude_candidates:
        claude_results = await _call_claude(
            claude_candidates, valid_accounts, policy, settings_obj,
            daily_burn_minor=daily_burn_minor,
            projected_month_spend_minor=projected_month_spend_minor,
        )
        for r in claude_results:
            claude_map[r.expense_id] = r
            if r.spend_category_summary and spend_summary is None:
                spend_summary = r.spend_category_summary
            if r.burn_rate_assessment and burn_rate_assessment is None:
                burn_rate_assessment = r.burn_rate_assessment

    # Merge decisions
    decisions: list[_ExpenseDecision] = list(hard_rule_decisions.values())

    for expense in claude_candidates:
        claude_result = claude_map.get(expense.id)

        if claude_result is None:
            decisions.append(_ExpenseDecision(
                expense_id=expense.id,
                amount_cents=expense.amount_cents,
                category=expense.category,
                account_code=expense.account_code,
                flags=["claude_missing_result"],
                action="flag",
                reasoning="Claude did not return a result — flagged for manual review.",
                hard_rule_applied=False,
            ))
            continue

        action = claude_result.recommended_action

        # 5. Policy: never auto-approve above auto_approve_limit_cents
        if action == "approve" and expense.amount_cents > policy.auto_approve_limit_cents:
            action = "flag"
            flags = [
                f"auto_approve blocked: amount {expense.amount_cents} exceeds "
                f"auto_approve_limit_cents {policy.auto_approve_limit_cents}"
            ]
            reasoning = (
                f"{claude_result.reasoning} — escalated: amount exceeds auto-approve limit."
            )
        else:
            flags = []
            reasoning = claude_result.reasoning

        decisions.append(_ExpenseDecision(
            expense_id=expense.id,
            amount_cents=expense.amount_cents,
            category=expense.category,
            account_code=expense.account_code,
            flags=flags,
            action=action,
            reasoning=reasoning,
            hard_rule_applied=False,
        ))

    # Derive overall decision
    has_block = any(d.action == "block" for d in decisions)
    has_flag = any(d.action == "flag" for d in decisions)

    if has_block:
        overall_decision = "blocked"
    elif has_flag:
        overall_decision = "approval_required"
    else:
        overall_decision = "auto_approved"

    violation_count = sum(1 for d in decisions if d.flags)
    confidence = round(
        1.0 - (violation_count / len(decisions))
        if overall_decision == "auto_approved"
        else violation_count / len(decisions),
        4,
    )

    reasoning_trace = {
        "overall_decision": overall_decision,
        "expense_count": len(decisions),
        "period_days": period_days,
        "daily_burn_minor": daily_burn_minor,
        "projected_month_spend_minor": projected_month_spend_minor,
        "high_burn_rate": high_burn_rate,
        "burn_rate_assessment": burn_rate_assessment,
        "policy": policy.model_dump(),
        "spend_category_summary": spend_summary,
        "per_expense": [
            {
                "expense_id": d.expense_id,
                "amount_cents": d.amount_cents,
                "category": d.category,
                "account_code": d.account_code,
                "flags": d.flags,
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

    actions_taken: list[str] = []
    block_ids = [d.expense_id for d in decisions if d.action == "block"]
    flag_ids = [d.expense_id for d in decisions if d.action == "flag"]

    if block_ids:
        actions_taken.append(f"blocked {len(block_ids)} expense(s)")
    if flag_ids:
        actions_taken.append(f"flagged {len(flag_ids)} expense(s) for review")
    if not block_ids and not flag_ids:
        actions_taken.append("all expenses approved — no status change")

    return {
        "decision": overall_decision,
        "confidence": confidence,
        "reasoning": json.dumps(reasoning_trace),
        "actions_taken": actions_taken,
        "output_data": reasoning_trace,
    }


async def run_expense_control_job(
    ctx: dict,
    *,
    execution_id: str,
    tenant_id: str,
    tool_id: str,
) -> dict:
    db = get_db()
    settings_obj = get_settings()
    start_ms = int(time.time() * 1000)

    try:
        result = await _execute_expense_control(tenant_id, tool_id, execution_id)
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


class ExpenseControlTool(BaseTool):
    TOOL_TYPE = ToolType.EXPENSE_CONTROL
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> ToolOutput:
        execution_id: str = input_data["execution_id"]
        tool_id: str = input_data["tool_id"]

        result = await _execute_expense_control(tenant_id, tool_id, execution_id)
        return ToolOutput(
            tool_type=self.TOOL_TYPE,
            decision=result["decision"],
            confidence=result["confidence"],
            reasoning=result["reasoning"],
            actions_taken=result["actions_taken"],
            output_data=result["output_data"],
        )
