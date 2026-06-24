"""
Budgeting Tool — sub-agent tool. Called by Financial Orchestrator as a tool.
Compares actual spend against active budget targets. Flags departments over
threshold and produces a variance analysis with run-rate projections, category
rollups, and period-adjusted policy thresholds.
"""
from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from anthropic import APIConnectionError, APIStatusError, AsyncAnthropic
from pydantic import BaseModel

from app.audit.logger import write_audit_log
from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.queue.pool import push_to_dlq
from app.tools.base import BaseTool, ToolOutput, ToolType

logger = get_logger(__name__)

_ACTOR = "tool:budgeting:v1"
_MODEL_VERSION = "budgeting-v1"
TOOL_TYPE = ToolType.BUDGETING


class _ToolPolicy(BaseModel):
    over_budget_alert_pct: float = 0.10
    critical_overspend_pct: float = 0.25


def _parse_policy(config_json: dict) -> _ToolPolicy:
    raw = config_json.get("policy", config_json)
    return _ToolPolicy(
        over_budget_alert_pct=raw.get("over_budget_alert_pct", 0.10),
        critical_overspend_pct=raw.get("critical_overspend_pct", 0.25),
    )


class _LineVariance(BaseModel):
    budget_line_id: str
    department: str | None
    category: str
    budget_cents: int
    actual_cents: int
    variance_cents: int
    variance_pct: float
    projected_spend_cents: int
    projected_over_budget: bool
    status: str


def _period_utilization(period_start: datetime, period_end: datetime) -> tuple[float, int, int]:
    """Return (utilization_pct, elapsed_days, total_days)."""
    today = date.today()
    s = period_start.date() if isinstance(period_start, datetime) else period_start
    e = period_end.date() if isinstance(period_end, datetime) else period_end
    total = max((e - s).days, 1)
    elapsed = max(min((today - s).days, total), 0)
    return round(elapsed / total * 100, 2), elapsed, total


def _calculate_actuals(expenses, bills, budget_start: datetime, budget_end: datetime) -> dict[str, int]:
    def in_period(dt) -> bool:
        if dt is None:
            return False
        if not isinstance(dt, datetime):
            dt = datetime(dt.year, dt.month, dt.day, tzinfo=UTC)
        return budget_start <= dt <= budget_end

    actuals: dict[str, int] = {}
    for exp in expenses:
        if in_period(exp.expense_date):
            k = (exp.category or "other").lower()
            actuals[k] = actuals.get(k, 0) + exp.amount_cents
    for bill in bills:
        if in_period(bill.issue_date):
            actuals["bills"] = actuals.get("bills", 0) + bill.total_cents
    return actuals


def _build_variances(
    lines, actuals: dict[str, int], policy: _ToolPolicy, elapsed: int, total: int
) -> list[_LineVariance]:
    out: list[_LineVariance] = []
    for line in lines:
        cat_key = (line.category or "other").lower()
        actual = actuals.get(cat_key, 0)
        variance = actual - line.amount_cents
        pct = variance / line.amount_cents if line.amount_cents > 0 else 0.0
        projected = int(actual / elapsed * total) if elapsed > 0 else 0
        if pct >= policy.critical_overspend_pct:
            status = "critical"
        elif pct >= policy.over_budget_alert_pct:
            status = "over_budget"
        elif pct >= 0:
            status = "on_track"
        else:
            status = "under_budget"
        out.append(_LineVariance(
            budget_line_id=line.id,
            department=getattr(line, "department", None),
            category=line.category,
            budget_cents=line.amount_cents,
            actual_cents=actual,
            variance_cents=variance,
            variance_pct=round(pct * 100, 2),
            projected_spend_cents=projected,
            projected_over_budget=projected > line.amount_cents,
            status=status,
        ))
    return out


def _category_rollup(lines, actuals: dict[str, int]) -> dict:
    rollup: dict = defaultdict(lambda: {"budget_cents": 0, "actual_cents": 0, "lines": []})
    for ln in lines:
        cat = ln.category or "Uncategorized"
        rollup[cat]["budget_cents"] += ln.amount_cents
        rollup[cat]["actual_cents"] += actuals.get(cat.lower(), 0)
        rollup[cat]["lines"].append(ln.name if hasattr(ln, "name") else ln.id)
    return dict(rollup)


def _period_adjusted_decision(
    has_critical: bool, over_items: list, variances: list[_LineVariance], util_pct: float
) -> tuple[str, float]:
    conf = 0.92 if util_pct >= 20.0 else 0.75
    all_close = all(v.actual_cents <= v.budget_cents * 1.05 for v in variances)
    if util_pct > 80.0 and all_close:
        return "auto_approved", conf
    if util_pct < 50.0 and any(v.actual_cents >= v.budget_cents * 0.9 for v in variances):
        return "approval_required", conf
    if has_critical:
        return "approval_required", conf
    if over_items or any(v.projected_over_budget for v in variances):
        return "approval_required", conf
    return "auto_approved", conf


def _build_prompt(
    variances: list[_LineVariance], rollup: dict, budget_name: str,
    policy: _ToolPolicy, util_pct: float, days_remaining: int,
) -> str:
    over_count = sum(1 for v in variances if v.status in ("over_budget", "critical"))
    total_b = sum(v.budget_cents for v in variances)
    total_a = sum(v.actual_cents for v in variances)
    fields = (
        '"variance_summary":string, "over_budget_items":string[], "critical_items":string[], '
        '"has_critical_overspend":boolean, "total_variance_pct":number, "recommendations":string[](max 3), '
        '"at_risk_categories":string[](max 3), "spending_pattern":"seasonal_spike"|"trending_up"|"trending_down"|"steady", '
        '"top_recommendation":string'
    )
    return (
        f"You are a financial planning analyst. Return ONLY valid JSON with these fields:\n{{{fields}}}\n\n"
        f"Budget:{budget_name} | Period:{util_pct:.1f}% elapsed,{days_remaining}d remaining\n"
        f"Total budget:{total_b}c | Actual:{total_a}c | Over threshold:{over_count}\n"
        f"Alert:{int(policy.over_budget_alert_pct*100)}% | Critical:{int(policy.critical_overspend_pct*100)}%\n\n"
        f"Line variances:\n{json.dumps([v.model_dump() for v in variances],indent=2)}\n\n"
        f"Category rollup:\n{json.dumps(rollup,indent=2)}"
    )


async def _call_claude(
    variances: list[_LineVariance], rollup: dict, budget_name: str,
    policy: _ToolPolicy, util_pct: float, days_remaining: int, settings_obj,
) -> dict:
    client = AsyncAnthropic(api_key=settings_obj.anthropic_api_key)
    prompt = _build_prompt(variances, rollup, budget_name, policy, util_pct, days_remaining)
    last_exc: Exception | None = None
    for attempt in range(settings_obj.max_agent_attempts):
        try:
            msg = await client.messages.create(
                model=settings_obj.claude_model,
                max_tokens=900,
                messages=[{"role": "user", "content": prompt}],
            )
            return json.loads(msg.content[0].text.strip())
        except (APIStatusError, APIConnectionError) as exc:
            last_exc = exc
            logger.error("claude_api_error", extra={"attempt": attempt + 1, "error": str(exc)})
            if attempt < settings_obj.max_agent_attempts - 1:
                await asyncio.sleep(settings_obj.backoff_seconds * (attempt + 1))
        except (json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError(f"Claude returned unparseable response: {exc}") from exc
    raise RuntimeError(f"Claude API failed after {settings_obj.max_agent_attempts} attempts: {last_exc}")


async def _execute(tenant_id: str, tool_id: str, execution_id: str, payload: dict) -> dict:
    settings_obj = get_settings()
    db = get_db()

    tool = await db.tool.find_first(where={"id": tool_id, "tenant_id": tenant_id})
    if tool is None:
        raise ValueError(f"Tool {tool_id} not found for tenant {tenant_id}")

    policy = _parse_policy(tool.config_json if isinstance(tool.config_json, dict) else {})
    now = datetime.now(UTC)
    active_budget = await db.budget.find_first(
        where={"tenant_id": tenant_id, "status": "active",
               "period_start": {"lte": now}, "period_end": {"gte": now}},
        include={"lines": True},
        order={"created_at": "desc"},
    )

    if active_budget is None or not active_budget.lines:
        await write_audit_log(
            tenant_id=tenant_id, actor=_ACTOR, action="budgeting:no_data",
            reasoning_trace={"reason": "no_active_budget"},
            model_version=_MODEL_VERSION, execution_id=execution_id,
        )
        return {"decision": "no_action", "confidence": 1.0,
                "reasoning": "No active budget found for the current period.",
                "actions_taken": [], "output_data": {"active_budget": False}}

    budget_start = active_budget.period_start
    budget_end = active_budget.period_end
    if not isinstance(budget_start, datetime):
        budget_start = datetime(budget_start.year, budget_start.month, budget_start.day, tzinfo=UTC)
    if not isinstance(budget_end, datetime):
        budget_end = datetime(budget_end.year, budget_end.month, budget_end.day, 23, 59, 59, tzinfo=UTC)

    util_pct, elapsed_days, total_days = _period_utilization(budget_start, budget_end)
    days_remaining = total_days - elapsed_days

    expenses, bills = await asyncio.gather(
        db.accountingexpense.find_many(where={"tenant_id": tenant_id}),
        db.accountingbill.find_many(where={"tenant_id": tenant_id}),
    )
    actuals = _calculate_actuals(expenses, bills, budget_start, budget_end)
    variances = _build_variances(active_budget.lines, actuals, policy, elapsed_days, total_days)
    rollup = _category_rollup(active_budget.lines, actuals)

    claude_result = await _call_claude(
        variances, rollup, active_budget.name, policy, util_pct, days_remaining, settings_obj,
    )
    has_critical = claude_result.get("has_critical_overspend", False)
    over_items = claude_result.get("over_budget_items", [])
    overall, confidence = _period_adjusted_decision(has_critical, over_items, variances, util_pct)

    reasoning_trace = {
        "overall_decision": overall,
        "budget_id": active_budget.id,
        "budget_name": active_budget.name,
        "period_start": budget_start.date().isoformat(),
        "period_end": budget_end.date().isoformat(),
        "period_utilization_pct": util_pct,
        "days_remaining": days_remaining,
        "policy": policy.model_dump(),
        "variances": [v.model_dump() for v in variances],
        "category_rollup": rollup,
        "claude_result": claude_result,
        "spending_pattern": claude_result.get("spending_pattern"),
        "top_recommendation": claude_result.get("top_recommendation"),
        "at_risk_categories": claude_result.get("at_risk_categories", []),
    }
    await write_audit_log(
        tenant_id=tenant_id, actor=_ACTOR, action=f"budgeting:{overall}",
        reasoning_trace=reasoning_trace, model_version=_MODEL_VERSION, execution_id=execution_id,
    )

    actions_taken = [
        f"checked {len(variances)} budget line(s) against actuals",
        f"{len(over_items)} line(s) over budget",
        f"period {util_pct:.1f}% elapsed, {days_remaining} day(s) remaining",
    ]
    if has_critical:
        actions_taken.append(f"critical overspend on: {', '.join(claude_result.get('critical_items', []))}")

    return {
        "decision": overall, "confidence": confidence,
        "reasoning": json.dumps(reasoning_trace),
        "actions_taken": actions_taken, "output_data": reasoning_trace,
    }


async def run_budgeting_job(
    ctx: dict, *, execution_id: str, tenant_id: str,
    tool_id: str, payload: dict, policy_config: dict,
) -> dict:
    db = get_db()
    settings_obj = get_settings()
    start_ms = int(time.time() * 1000)
    try:
        result = await _execute(tenant_id, tool_id, execution_id, payload)
        duration_ms = int(time.time() * 1000) - start_ms
        await db.execution.update(
            where={"id": execution_id},
            data={"status": "completed", "decision": result["decision"],
                  "confidence": result["confidence"], "duration_ms": duration_ms},
        )
        if result["decision"] == "approval_required":
            await db.approval.create(data={
                "tenant_id": tenant_id, "execution_id": execution_id,
                "expires_at": datetime.now(UTC) + timedelta(seconds=settings_obj.approval_ttl_seconds),
            })
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
                function_name="run_budgeting_job",
                error=str(exc),
            )
        raise


class BudgetingTool(BaseTool):
    TOOL_TYPE = ToolType.BUDGETING
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> ToolOutput:
        result = await _execute(
            tenant_id, input_data["tool_id"],
            input_data["execution_id"], input_data.get("payload", {}),
        )
        return ToolOutput(
            tool_type=self.TOOL_TYPE, decision=result["decision"],
            confidence=result["confidence"], reasoning=result["reasoning"],
            actions_taken=result["actions_taken"], output_data=result["output_data"],
        )
