"""
Spend Control Tool — sub-agent tool combining two AP/expense sub-flows, dispatched directly to its arq job as one tool:
  1. Expense Control — validates AccountingExpense records against policy limits, using the chart of accounts
     to detect miscategorised spend. Claude summarises spend by category and recommends approve|flag|block.
  2. Accounts Payable — classifies AP bills, detects duplicates, routes approvals, and recommends pay/block actions.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from anthropic import APIConnectionError, APIStatusError, AsyncAnthropic
from pydantic import BaseModel

from app.audit.logger import write_audit_log
from app.core.config import get_settings
from app.core.db import get_db
from app.core.execution import complete_execution
from app.core.logging import get_logger
from app.queue.pool import push_to_dlq
from app.tools.base import BaseTool, ToolOutput, ToolType

logger = get_logger(__name__)



# ============================================================
# Expense Control
# ============================================================

_EXPENSE_ACTOR = "tool:expense_control:v1"
_EXPENSE_MODEL_VERSION = "expense_control-v1"
_ACTION_RANK: dict[str, int] = {"approve": 0, "flag": 1, "block": 2}

# Round-number check: multiples of $100 (10 000 cents) above $500 (50 000 cents)
_ROUND_NUMBER_MODULUS: int = 10_000
_ROUND_NUMBER_MIN_CENTS: int = 50_000


class _ExpenseToolPolicy(BaseModel):
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


def _parse_expense_policy(config_json: dict) -> _ExpenseToolPolicy:
    raw = config_json.get("policy", config_json)
    return _ExpenseToolPolicy.model_validate({k: v for k, v in raw.items() if k in _ExpenseToolPolicy.model_fields})


def _apply_hard_rules(
    expense: _ExpenseRecord,
    valid_account_codes: set[str],
    policy: _ExpenseToolPolicy,
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


async def _call_claude_expense(
    expenses: list[_ExpenseRecord],
    valid_accounts: list[_AccountRecord],
    policy: _ExpenseToolPolicy,
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
    policy = _parse_expense_policy(config_raw)

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
            actor=_EXPENSE_ACTOR,
            action="expense_control:auto_approved",
            reasoning_trace=reasoning_trace,
            model_version=_EXPENSE_MODEL_VERSION,
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
        claude_results = await _call_claude_expense(
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
        actor=_EXPENSE_ACTOR,
        action=f"expense_control:{overall_decision}",
        reasoning_trace=reasoning_trace,
        model_version=_EXPENSE_MODEL_VERSION,
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
    transaction_ids: list[str] | None = None,
) -> dict:
    # transaction_ids is accepted for dispatch compatibility (the tool_type and
    # event paths both pass it); this job scans all pending expenses regardless.
    db = get_db()
    start_ms = int(time.time() * 1000)

    try:
        result = await _execute_expense_control(tenant_id, tool_id, execution_id)
        duration_ms = int(time.time() * 1000) - start_ms
        # complete_execution applies the autonomy override, writes the final decision,
        # creates the Approval when required, and advances the workflow (advance_workflow
        # is called inside it) — the single canonical finalization path for every tool.
        final_decision = await complete_execution(
            db=db, execution_id=execution_id, tool_id=tool_id,
            tenant_id=tenant_id, decision=result["decision"],
            confidence=result["confidence"], duration_ms=duration_ms,
        )
        return {**result, "decision": final_decision}
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


# ============================================================
# Accounts Payable
# ============================================================

_AP_ACTOR = "tool:accounts_payable:v1"
_AP_MODEL_VERSION = "accounts_payable-v1"
class _APToolPolicy(BaseModel):
    auto_pay_limit_cents: int = 50_000
    approval_threshold_cents: int = 100_000
    duplicate_window_days: int = 30


class _BillRecord(BaseModel):
    id: str
    vendor_id: str | None
    contact_name: str | None
    total_cents: int
    outstanding_cents: int
    issue_date: date | None
    due_date: date | None
    status: str
    payment_terms: str | None = None
    is_duplicate: bool = False
    requires_approval: bool = False
    early_payment_discount_available: bool = False
    early_payment_discount_pct: float = 0.0
    early_payment_discount_cents: int = 0


class _ClaudeBillResult(BaseModel):
    bill_id: str
    classification: Literal["routine", "suspicious", "duplicate", "approval_required"]
    recommendation: Literal["auto_pay", "request_approval", "flag_duplicate", "block", "batch_pay"]
    reasoning: str


def _parse_ap_policy(config_json: dict) -> _APToolPolicy:
    raw = config_json.get("policy", config_json)
    return _APToolPolicy(
        auto_pay_limit_cents=raw.get("auto_pay_limit_cents", 50_000),
        approval_threshold_cents=raw.get("approval_threshold_cents", 100_000),
        duplicate_window_days=raw.get("duplicate_window_days", 30),
    )


def _detect_duplicates(bills: list[_BillRecord], window_days: int) -> None:
    """Mark bills as duplicate in-place: same contact + total + issue_date within window."""
    seen: dict[str, list[_BillRecord]] = {}
    for bill in bills:
        key = f"{bill.contact_name}|{bill.total_cents}"
        seen.setdefault(key, []).append(bill)

    for group in seen.values():
        if len(group) < 2:
            continue
        sorted_group = sorted(group, key=lambda b: b.issue_date or date.min)
        for i, bill in enumerate(sorted_group):
            for other in sorted_group[i + 1:]:
                if bill.issue_date and other.issue_date:
                    delta = abs((other.issue_date - bill.issue_date).days)
                    if delta <= window_days:
                        bill.is_duplicate = True
                        other.is_duplicate = True


_DISCOUNT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)/(\d+)", re.IGNORECASE)


def _detect_early_payment_discounts(bills: list[_BillRecord]) -> None:
    """Parse payment_terms for early payment discounts (e.g. '2/10 net 30') and annotate bills in-place."""
    today = date.today()
    for bill in bills:
        if not bill.payment_terms or not bill.issue_date:
            continue
        match = _DISCOUNT_PATTERN.search(bill.payment_terms)
        if not match:
            continue
        discount_pct = float(match.group(1))
        discount_days = int(match.group(2))
        days_since_issue = (today - bill.issue_date).days
        if days_since_issue <= discount_days:
            bill.early_payment_discount_available = True
            bill.early_payment_discount_pct = discount_pct
            bill.early_payment_discount_cents = round(bill.outstanding_cents * discount_pct / 100)


def _group_by_supplier(bills: list[_BillRecord]) -> list[dict]:
    """Return supplier groups where a vendor has multiple outstanding bills."""
    groups: dict[str, list[_BillRecord]] = {}
    for bill in bills:
        key = bill.vendor_id or bill.contact_name or bill.id
        groups.setdefault(key, []).append(bill)
    return [
        {
            "supplier_id": key,
            "bill_ids": [b.id for b in group],
            "bill_count": len(group),
            "supplier_total_minor": sum(b.outstanding_cents for b in group),
        }
        for key, group in groups.items()
        if len(group) > 1
    ]


def _build_prompt(bills: list[_BillRecord], supplier_groups: list[dict]) -> str:
    bill_data = [
        {
            "bill_id": b.id, "vendor_id": b.vendor_id, "contact_name": b.contact_name,
            "total_cents": b.total_cents, "outstanding_cents": b.outstanding_cents,
            "issue_date": b.issue_date.isoformat() if b.issue_date else None,
            "due_date": b.due_date.isoformat() if b.due_date else None,
            "status": b.status,
            "early_payment_discount_available": b.early_payment_discount_available,
            "early_payment_discount_pct": b.early_payment_discount_pct,
            "pre_flagged_duplicate": b.is_duplicate,
            "pre_flagged_approval_required": b.requires_approval,
        }
        for b in bills
    ]
    supplier_ctx = (
        f"\n\nSupplier groups (multiple bills from same supplier):\n{json.dumps(supplier_groups, indent=2)}"
        if supplier_groups else ""
    )
    return (
        "You are an accounts payable specialist. Analyse the bills below and return a JSON array "
        "— one object per bill — with exactly these fields:\n"
        '  "bill_id": string, "classification": "routine"|"suspicious"|"duplicate"|"approval_required",\n'
        '  "recommendation": "auto_pay"|"request_approval"|"flag_duplicate"|"block"|"batch_pay",\n'
        '  "reasoning": string\n\n'
        "Rules:\n"
        "- pre_flagged_duplicate=true → classification duplicate, recommendation flag_duplicate\n"
        "- pre_flagged_approval_required=true → classification approval_required, recommendation request_approval\n"
        "- early_payment_discount_available=true → prioritise for same-day payment; use auto_pay if within limit\n"
        "- Multiple bills with same vendor_id → recommend batch_pay to reduce transaction costs\n"
        "- Suspicious signals: round amounts, new/unknown vendors, mismatched dates\n"
        "Return ONLY a valid JSON array. No markdown, no prose."
        + supplier_ctx
        + f"\n\nBills:\n{json.dumps(bill_data, indent=2)}"
    )


async def _call_claude_ap(bills: list[_BillRecord], supplier_groups: list[dict], settings_obj) -> list[_ClaudeBillResult]:
    client = AsyncAnthropic(api_key=settings_obj.anthropic_api_key)
    prompt = _build_prompt(bills, supplier_groups)
    last_exc: Exception | None = None
    for attempt in range(settings_obj.max_agent_attempts):
        try:
            msg = await client.messages.create(model=settings_obj.claude_model, max_tokens=2048, messages=[{"role": "user", "content": prompt}])
            parsed = json.loads(msg.content[0].text.strip())
            if not isinstance(parsed, list):
                raise ValueError("Claude response is not a JSON array")
            return [_ClaudeBillResult(**item) for item in parsed]
        except (APIStatusError, APIConnectionError) as exc:
            last_exc = exc
            logger.error("claude_api_error", extra={"attempt": attempt + 1, "error": str(exc)})
            if attempt < settings_obj.max_agent_attempts - 1:
                await asyncio.sleep(settings_obj.backoff_seconds * (attempt + 1))
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            raise RuntimeError(f"Claude returned unparseable response: {exc}") from exc
    raise RuntimeError(f"Claude API failed after {settings_obj.max_agent_attempts} attempts: {last_exc}")


async def _execute_accounts_payable(tenant_id: str, tool_id: str, execution_id: str, payload: dict) -> dict:
    settings_obj = get_settings()
    db = get_db()

    tool = await db.tool.find_first(where={"id": tool_id, "tenant_id": tenant_id})
    if tool is None:
        raise ValueError(f"Tool {tool_id} not found for tenant {tenant_id}")

    policy = _parse_ap_policy(tool.config_json if isinstance(tool.config_json, dict) else {})

    raw = await db.accountingbill.find_many(
        where={
            "tenant_id": tenant_id,
            "status": {"not_in": ["paid", "void"]},
        },
        order={"due_date": "asc"},
    )

    if not raw:
        await write_audit_log(tenant_id=tenant_id, actor=_AP_ACTOR, action="accounts_payable:no_action",
                              reasoning_trace={"reason": "no_outstanding_bills"}, model_version=_AP_MODEL_VERSION, execution_id=execution_id)
        return {"decision": "no_action", "confidence": 1.0, "reasoning": "No outstanding bills found.", "actions_taken": [], "output_data": {"bill_count": 0}}

    def _to_date(val):
        return val.date() if isinstance(val, datetime) else val

    bills: list[_BillRecord] = [
        _BillRecord(
            id=b.id,
            vendor_id=getattr(b, "vendor_id", None) or getattr(b, "contact_id", None),
            contact_name=getattr(b, "contact_name", None),
            total_cents=b.total_cents, outstanding_cents=b.outstanding_cents,
            issue_date=_to_date(b.issue_date), due_date=_to_date(b.due_date),
            status=b.status, payment_terms=getattr(b, "payment_terms", None),
            requires_approval=b.total_cents > policy.approval_threshold_cents,
        )
        for b in raw
    ]

    _detect_duplicates(bills, policy.duplicate_window_days)
    _detect_early_payment_discounts(bills)

    supplier_groups = _group_by_supplier(bills)
    claude_results = await _call_claude_ap(bills, supplier_groups, settings_obj)
    claude_map = {r.bill_id: r for r in claude_results}

    # Policy check: never auto_pay above limit
    policy_overrides: list[str] = []
    for result in claude_results:
        if result.recommendation in ("auto_pay", "batch_pay"):
            bill = next((b for b in bills if b.id == result.bill_id), None)
            if bill and bill.total_cents > policy.auto_pay_limit_cents:
                result.recommendation = "request_approval"
                policy_overrides.append(
                    f"auto_pay blocked for bill {result.bill_id} "
                    f"(total {bill.total_cents} > limit {policy.auto_pay_limit_cents})"
                )

    has_block = any(r.recommendation == "block" for r in claude_results)
    has_approval = any(r.recommendation == "request_approval" for r in claude_results)
    has_duplicate = any(r.recommendation == "flag_duplicate" for r in claude_results)

    if has_block:
        overall = "blocked"
    elif has_approval:
        overall = "approval_required"
    elif has_duplicate:
        overall = "duplicates_flagged"
    else:
        overall = "auto_approved"

    confidence = 0.95 if overall == "auto_approved" else 0.85

    total_discount_available_minor = sum(b.early_payment_discount_cents for b in bills)
    bills_with_discount_count = sum(1 for b in bills if b.early_payment_discount_available)
    recommended_batch_payments = [
        {
            "supplier_id": g["supplier_id"],
            "bill_ids": g["bill_ids"],
            "total_minor": g["supplier_total_minor"],
        }
        for g in supplier_groups
    ]

    reasoning_trace = {
        "overall_decision": overall,
        "bill_count": len(bills),
        "total_discount_available_minor": total_discount_available_minor,
        "bills_with_discount_count": bills_with_discount_count,
        "recommended_batch_payments": recommended_batch_payments,
        "policy": policy.model_dump(),
        "policy_overrides": policy_overrides,
        "per_bill": [
            {**claude_map[b.id].model_dump(), "is_duplicate": b.is_duplicate}
            if b.id in claude_map else {"bill_id": b.id, "classification": "unscored"}
            for b in bills
        ],
    }

    await write_audit_log(tenant_id=tenant_id, actor=_AP_ACTOR, action=f"accounts_payable:{overall}",
                          reasoning_trace=reasoning_trace, model_version=_AP_MODEL_VERSION, execution_id=execution_id)

    duplicate_count = sum(1 for b in bills if b.is_duplicate)
    actions_taken = [f"assessed {len(bills)} bill(s)"]
    if policy_overrides:
        actions_taken.extend(policy_overrides)
    if duplicate_count:
        actions_taken.append(f"flagged {duplicate_count} duplicate bill(s)")
    if bills_with_discount_count:
        actions_taken.append(f"identified {bills_with_discount_count} bill(s) with early payment discounts totalling {total_discount_available_minor} minor units")
    if recommended_batch_payments:
        actions_taken.append(f"recommended {len(recommended_batch_payments)} batch payment(s)")

    return {
        "decision": overall,
        "confidence": confidence,
        "reasoning": json.dumps(reasoning_trace),
        "actions_taken": actions_taken,
        "output_data": reasoning_trace,
    }


async def run_accounts_payable_job(ctx: dict, *, execution_id: str, tenant_id: str, tool_id: str, payload: dict, policy_config: dict) -> dict:
    db = get_db()
    start_ms = int(time.time() * 1000)
    try:
        result = await _execute_accounts_payable(tenant_id, tool_id, execution_id, payload)
        duration_ms = int(time.time() * 1000) - start_ms
        # Canonical finalization: complete_execution applies the autonomy override,
        # writes the final decision, and creates the Approval when required.
        final_decision = await complete_execution(
            db=db, execution_id=execution_id, tool_id=tool_id,
            tenant_id=tenant_id, decision=result["decision"],
            confidence=result["confidence"], duration_ms=duration_ms,
        )
        return {**result, "decision": final_decision}
    except Exception as exc:
        try:
            await db.execution.update(where={"id": execution_id}, data={"status": "failed", "decision": "failed"})
        except Exception:
            pass
        if ctx.get("job_try", 1) >= 3:
            await push_to_dlq(job_id=str(ctx.get("job_id", "unknown")), function_name="run_accounts_payable_job", error=str(exc))
        raise


class AccountsPayableTool(BaseTool):
    TOOL_TYPE = ToolType.SPEND_CONTROL
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> ToolOutput:
        result = await _execute_accounts_payable(tenant_id, input_data["tool_id"], input_data["execution_id"], input_data.get("payload", {}))
        return ToolOutput(
            tool_type=self.TOOL_TYPE, decision=result["decision"], confidence=result["confidence"],
            reasoning=result["reasoning"], actions_taken=result["actions_taken"], output_data=result["output_data"],
        )
