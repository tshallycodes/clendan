"""
Budgeting Tool — sub-agent tool. Called by Financial Orchestrator as a tool.
Compares actual spend against active budget targets. Flags departments over threshold
and produces a variance analysis with recommendations.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime, timedelta

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
    status: str


def _calculate_actuals(expenses, bills, budget_start: datetime, budget_end: datetime) -> dict[str, int]:
    actuals: dict[str, int] = {}

    def in_period(dt) -> bool:
        if dt is None:
            return False
        if not isinstance(dt, datetime):
            dt = datetime(dt.year, dt.month, dt.day, tzinfo=UTC)
        return budget_start <= dt <= budget_end

    for expense in expenses:
        if not in_period(expense.expense_date):
            continue
        cat = (expense.category or "other").lower()
        actuals[cat] = actuals.get(cat, 0) + expense.amount_cents

    for bill in bills:
        if not in_period(bill.issue_date):
            continue
        cat = "bills"
        actuals[cat] = actuals.get(cat, 0) + bill.total_cents

    return actuals


def _build_variances(lines, actuals: dict[str, int], policy: _ToolPolicy) -> list[_LineVariance]:
    variances: list[_LineVariance] = []

    for line in lines:
        cat_key = (line.category or "other").lower()
        actual = actuals.get(cat_key, 0)
        variance = actual - line.amount_cents
        pct = variance / line.amount_cents if line.amount_cents > 0 else 0.0

        if pct >= policy.critical_overspend_pct:
            status = "critical"
        elif pct >= policy.over_budget_alert_pct:
            status = "over_budget"
        elif pct >= 0:
            status = "on_track"
        else:
            status = "under_budget"

        variances.append(_LineVariance(
            budget_line_id=line.id,
            department=getattr(line, "department", None),
            category=line.category,
            budget_cents=line.amount_cents,
            actual_cents=actual,
            variance_cents=variance,
            variance_pct=round(pct * 100, 2),
            status=status,
        ))

    return variances


def _build_prompt(variances: list[_LineVariance], budget_name: str, policy: _ToolPolicy) -> str:
    data = [v.model_dump() for v in variances]
    over = [v for v in variances if v.status in ("over_budget", "critical")]
    total_budget = sum(v.budget_cents for v in variances)
    total_actual = sum(v.actual_cents for v in variances)

    return (
        "You are a financial planning analyst. Analyse the budget variance data below and return a JSON object "
        "with exactly these fields:\n"
        '  "variance_summary": string (2-3 sentences: overall budget health, biggest variances),\n'
        '  "over_budget_items": array of strings (category names that are over budget — empty if none),\n'
        '  "critical_items": array of strings (category names with critical overspend — empty if none),\n'
        '  "has_critical_overspend": boolean,\n'
        '  "total_variance_pct": number (overall actual vs budget as a percentage),\n'
        '  "recommendations": array of up to 3 specific action strings\n\n'
        f"Budget: {budget_name}\n"
        f"Total budget: {total_budget} cents | Total actual: {total_actual} cents\n"
        f"Alert threshold: {int(policy.over_budget_alert_pct * 100)}% over | "
        f"Critical threshold: {int(policy.critical_overspend_pct * 100)}% over\n"
        f"Items over budget: {len(over)}\n\n"
        "Return ONLY valid JSON. No markdown, no prose.\n\n"
        f"Variance data:\n{json.dumps(data, indent=2)}"
    )


async def _call_claude(
    variances: list[_LineVariance], budget_name: str, policy: _ToolPolicy, settings_obj
) -> dict:
    client = AsyncAnthropic(api_key=settings_obj.anthropic_api_key)
    prompt = _build_prompt(variances, budget_name, policy)
    last_exc: Exception | None = None

    for attempt in range(settings_obj.max_agent_attempts):
        try:
            message = await client.messages.create(
                model=settings_obj.claude_model,
                max_tokens=768,
                messages=[{"role": "user", "content": prompt}],
            )
            return json.loads(message.content[0].text.strip())
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
        where={
            "tenant_id": tenant_id,
            "status": "active",
            "period_start": {"lte": now},
            "period_end": {"gte": now},
        },
        include={"lines": True},
        order={"created_at": "desc"},
    )

    if active_budget is None or not active_budget.lines:
        await write_audit_log(
            tenant_id=tenant_id,
            actor=_ACTOR,
            action="budgeting:no_data",
            reasoning_trace={"reason": "no_active_budget"},
            model_version=_MODEL_VERSION,
            execution_id=execution_id,
        )
        return {
            "decision": "no_action",
            "confidence": 1.0,
            "reasoning": "No active budget found for the current period.",
            "actions_taken": [],
            "output_data": {"active_budget": False},
        }

    budget_start = active_budget.period_start
    budget_end = active_budget.period_end

    if not isinstance(budget_start, datetime):
        budget_start = datetime(budget_start.year, budget_start.month, budget_start.day, tzinfo=UTC)
    if not isinstance(budget_end, datetime):
        budget_end = datetime(budget_end.year, budget_end.month, budget_end.day, 23, 59, 59, tzinfo=UTC)

    expenses, bills = await asyncio.gather(
        db.accountingexpense.find_many(where={"tenant_id": tenant_id}),
        db.accountingbill.find_many(where={"tenant_id": tenant_id}),
    )

    actuals = _calculate_actuals(expenses, bills, budget_start, budget_end)
    variances = _build_variances(active_budget.lines, actuals, policy)

    claude_result = await _call_claude(variances, active_budget.name, policy, settings_obj)

    has_critical = claude_result.get("has_critical_overspend", False)
    over_budget_items = claude_result.get("over_budget_items", [])

    if has_critical:
        overall = "approval_required"
        confidence = 0.88
    elif over_budget_items:
        overall = "approval_required"
        confidence = 0.90
    else:
        overall = "auto_approved"
        confidence = 0.95

    reasoning_trace = {
        "overall_decision": overall,
        "budget_id": active_budget.id,
        "budget_name": active_budget.name,
        "period_start": budget_start.date().isoformat(),
        "period_end": budget_end.date().isoformat(),
        "policy": policy.model_dump(),
        "variances": [v.model_dump() for v in variances],
        "claude_result": claude_result,
    }

    await write_audit_log(
        tenant_id=tenant_id,
        actor=_ACTOR,
        action=f"budgeting:{overall}",
        reasoning_trace=reasoning_trace,
        model_version=_MODEL_VERSION,
        execution_id=execution_id,
    )

    actions_taken = [
        f"checked {len(variances)} budget line(s) against actuals",
        f"{len(over_budget_items)} line(s) over budget",
    ]
    if has_critical:
        critical = claude_result.get("critical_items", [])
        actions_taken.append(f"critical overspend on: {', '.join(critical)}")

    return {
        "decision": overall,
        "confidence": confidence,
        "reasoning": json.dumps(reasoning_trace),
        "actions_taken": actions_taken,
        "output_data": reasoning_trace,
    }


async def run_budgeting_job(
    ctx: dict,
    *,
    execution_id: str,
    tenant_id: str,
    tool_id: str,
    payload: dict,
    policy_config: dict,
) -> dict:
    db = get_db()
    settings_obj = get_settings()
    start_ms = int(time.time() * 1000)

    try:
        result = await _execute(tenant_id, tool_id, execution_id, payload)
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
                    "expires_at": datetime.now(UTC) + timedelta(seconds=settings_obj.approval_ttl_seconds),
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
                function_name="run_budgeting_job",
                error=str(exc),
            )
        raise


class BudgetingTool(BaseTool):
    TOOL_TYPE = ToolType.BUDGETING
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> ToolOutput:
        result = await _execute(
            tenant_id,
            input_data["tool_id"],
            input_data["execution_id"],
            input_data.get("payload", {}),
        )
        return ToolOutput(
            tool_type=self.TOOL_TYPE,
            decision=result["decision"],
            confidence=result["confidence"],
            reasoning=result["reasoning"],
            actions_taken=result["actions_taken"],
            output_data=result["output_data"],
        )
