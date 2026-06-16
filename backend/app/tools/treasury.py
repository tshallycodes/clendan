"""
Treasury Tool — sub-agent tool. Called by Financial Orchestrator as a tool.
Monitors cash position across all bank accounts, forecasts runway, and alerts when
balances fall below configured thresholds. Claude analyses spending patterns and
produces a cash flow forecast.
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

_ACTOR = "tool:treasury:v1"
_MODEL_VERSION = "treasury-v1"


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


class _ToolPolicy(BaseModel):
    min_balance_alert: int = 1000000                      # pence — alert if total balance below this
    cash_runway_warning_days: int = 90                    # alert if forecast runway < this many days
    forecast_horizon_days: int = 30                       # look this far back for spending rate
    minimum_operating_balance_alert_days: int = 45        # days of expenses — better than fixed amount
    critical_balance_alert_days: int = 14
    runway_alert_days: int = 90
    runway_critical_days: int = 30
    forecast_update_frequency: str = "weekly"             # "daily" | "weekly" | "monthly"
    forecast_method: str = "hybrid"                       # "simple_moving_avg" | "weighted_moving_avg" | "ml_forecast" | "hybrid"
    cash_sweep_enabled: bool = False                      # Dangerous if miscalibrated — off by default
    cash_sweep_threshold: int = 50000000                  # minor units ($500,000)
    cash_sweep_retain_minimum: int = 10000000             # minor units ($100,000)
    bank_counterparty_limit: int = 25000000               # minor units ($250,000) — FDIC ceiling
    bank_counterparty_count_min: int = 2
    investment_max_single_counterparty_pct: float = 0.25
    fx_exposure_alert_pct: float = 0.20
    ar_aging_visibility_enabled: bool = True
    payroll_reserve_days: int = 5
    daily_reconciliation_enabled: bool = True


# ---------------------------------------------------------------------------
# Internal data models
# ---------------------------------------------------------------------------


class _AccountSummary(BaseModel):
    id: str
    name: str
    type: str
    current_balance_minor: int
    currency: str


class _TransactionSummary(BaseModel):
    id: str
    account_id: str
    amount_minor: int
    date: datetime
    description: str | None
    category: str | None


class _ClaudeResult(BaseModel):
    total_balance_minor: int
    avg_daily_spend_minor: int
    forecast_runway_days: int
    alerts: list[str]
    recommended_action: Literal["ok", "review", "alert"]
    reasoning: str


# ---------------------------------------------------------------------------
# Policy parser
# ---------------------------------------------------------------------------


def _parse_policy(config_json: dict) -> _ToolPolicy:
    raw = config_json.get("policy", config_json)
    return _ToolPolicy(
        min_balance_alert=raw.get("min_balance_alert", 1000000),
        cash_runway_warning_days=raw.get("cash_runway_warning_days", 90),
        forecast_horizon_days=raw.get("forecast_horizon_days", 30),
        minimum_operating_balance_alert_days=raw.get("minimum_operating_balance_alert_days", 45),
        critical_balance_alert_days=raw.get("critical_balance_alert_days", 14),
        runway_alert_days=raw.get("runway_alert_days", 90),
        runway_critical_days=raw.get("runway_critical_days", 30),
        forecast_update_frequency=raw.get("forecast_update_frequency", "weekly"),
        forecast_method=raw.get("forecast_method", "hybrid"),
        cash_sweep_enabled=raw.get("cash_sweep_enabled", False),
        cash_sweep_threshold=raw.get("cash_sweep_threshold", 50000000),
        cash_sweep_retain_minimum=raw.get("cash_sweep_retain_minimum", 10000000),
        bank_counterparty_limit=raw.get("bank_counterparty_limit", 25000000),
        bank_counterparty_count_min=raw.get("bank_counterparty_count_min", 2),
        investment_max_single_counterparty_pct=raw.get("investment_max_single_counterparty_pct", 0.25),
        fx_exposure_alert_pct=raw.get("fx_exposure_alert_pct", 0.20),
        ar_aging_visibility_enabled=raw.get("ar_aging_visibility_enabled", True),
        payroll_reserve_days=raw.get("payroll_reserve_days", 5),
        daily_reconciliation_enabled=raw.get("daily_reconciliation_enabled", True),
    )


# ---------------------------------------------------------------------------
# Claude prompt + call
# ---------------------------------------------------------------------------


def _build_claude_prompt(
    accounts: list[_AccountSummary],
    recent_transactions: list[_TransactionSummary],
    policy: _ToolPolicy,
) -> str:
    accounts_json = json.dumps(
        [
            {
                "id": a.id,
                "name": a.name,
                "type": a.type,
                "current_balance_minor": a.current_balance_minor,
                "currency": a.currency,
            }
            for a in accounts
        ],
        indent=2,
    )
    transactions_json = json.dumps(
        [
            {
                "id": t.id,
                "account_id": t.account_id,
                "amount_minor": t.amount_minor,
                "date": t.date.isoformat(),
                "description": t.description,
                "category": t.category,
            }
            for t in recent_transactions
        ],
        indent=2,
    )
    return (
        "You are a treasury analyst. Analyse the bank accounts and recent transactions below.\n\n"
        "Tasks:\n"
        f"1. Calculate average daily spend (in minor currency units, i.e. pence/cents) from the "
        f"last {policy.forecast_horizon_days} days of transactions. "
        "Only outgoing amounts (negative amount_minor) count as spend.\n"
        "2. Forecast runway = total_balance_minor / avg_daily_spend_minor "
        "(use 1 as minimum denominator to avoid division by zero).\n"
        "3. Identify any unusual spending patterns (sudden spikes, abnormal categories, etc).\n\n"
        "Return ONLY a single JSON object — no markdown, no prose — with exactly these fields:\n"
        '  "total_balance_minor": integer (sum of all account balances),\n'
        '  "avg_daily_spend_minor": integer (average daily outflow in minor units),\n'
        '  "forecast_runway_days": integer (total_balance_minor / max(avg_daily_spend_minor, 1)),\n'
        '  "alerts": array of short alert strings (empty array if none),\n'
        '  "recommended_action": one of "ok" | "review" | "alert",\n'
        '  "reasoning": one concise paragraph.\n\n'
        f"Bank Accounts:\n{accounts_json}\n\n"
        f"Recent Transactions (last {policy.forecast_horizon_days} days):\n{transactions_json}"
    )


async def _call_claude(
    accounts: list[_AccountSummary],
    transactions: list[_TransactionSummary],
    policy: _ToolPolicy,
    settings_obj,
) -> _ClaudeResult:
    client = AsyncAnthropic(api_key=settings_obj.anthropic_api_key)
    prompt = _build_claude_prompt(accounts, transactions, policy)
    last_exc: Exception | None = None

    for attempt in range(settings_obj.max_agent_attempts):
        try:
            message = await client.messages.create(
                model=settings_obj.claude_model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = message.content[0].text.strip()
            parsed = json.loads(raw_text)
            if not isinstance(parsed, dict):
                raise ValueError("Claude response is not a JSON object")
            return _ClaudeResult(**parsed)
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


async def _execute_treasury(
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

    # Fetch all bank accounts for tenant
    raw_accounts = await db.bankaccount.find_many(
        where={"tenant_id": tenant_id}
    )
    if not raw_accounts:
        raise ValueError(f"No bank accounts found for tenant {tenant_id}")

    accounts = [
        _AccountSummary(
            id=a.id,
            name=a.name,
            type=a.type,
            current_balance_minor=a.current_balance_minor,
            currency=a.currency,
        )
        for a in raw_accounts
    ]

    # Integer arithmetic — no floats for currency
    total_balance_minor: int = sum(a.current_balance_minor for a in accounts)

    # Hard rule: low balance check BEFORE calling Claude
    alert_triggered: bool = total_balance_minor < policy.min_balance_alert

    # Fetch recent transactions scoped to tenant
    cutoff = datetime.now(UTC) - timedelta(days=policy.forecast_horizon_days)
    raw_txns = await db.banktransaction.find_many(
        where={
            "tenant_id": tenant_id,
            "date": {"gte": cutoff},
        }
    )

    recent_transactions = [
        _TransactionSummary(
            id=t.id,
            account_id=t.account_id,
            amount_minor=t.amount_minor,
            date=t.date,
            description=t.description,
            category=t.category,
        )
        for t in raw_txns
    ]

    # Call Claude for runway forecast and pattern analysis
    claude_result = await _call_claude(accounts, recent_transactions, policy, settings_obj)

    # Runway check — integer division, no floats
    safe_avg_daily = max(claude_result.avg_daily_spend_minor, 1)
    forecast_runway_days: int = total_balance_minor // safe_avg_daily
    runway_alert: bool = forecast_runway_days < policy.cash_runway_warning_days

    # Derive overall decision
    critically_low = total_balance_minor < (policy.min_balance_alert // 2)
    critically_short_runway = forecast_runway_days < (policy.cash_runway_warning_days // 2)

    if alert_triggered or runway_alert or claude_result.alerts:
        if critically_low or critically_short_runway:
            overall_decision = "approval_required"
        else:
            overall_decision = "approval_required"
    else:
        overall_decision = "auto_approved"

    # Confidence: higher when healthy, lower when alerts are present
    alert_count = len(claude_result.alerts)
    if overall_decision == "auto_approved":
        confidence = round(min(1.0, 0.90 + (0.02 * max(0, 5 - alert_count))), 4)
    else:
        confidence = round(max(0.50, 0.85 - (0.05 * alert_count)), 4)

    actions_taken: list[str] = []
    if alert_triggered:
        actions_taken.append(
            f"balance_alert: total balance {total_balance_minor} minor units is below "
            f"threshold {policy.min_balance_alert}"
        )
    if runway_alert:
        actions_taken.append(
            f"runway_alert: forecast runway {forecast_runway_days} days is below "
            f"warning threshold {policy.cash_runway_warning_days} days"
        )
    for alert in claude_result.alerts:
        actions_taken.append(f"pattern_alert: {alert}")
    if not actions_taken:
        actions_taken.append("cash position healthy — no alerts triggered")

    reasoning_trace: dict = {
        "overall_decision": overall_decision,
        "total_balance_minor": total_balance_minor,
        "avg_daily_spend_minor": claude_result.avg_daily_spend_minor,
        "forecast_runway_days": forecast_runway_days,
        "alert_triggered": alert_triggered,
        "runway_alert": runway_alert,
        "policy": policy.model_dump(),
        "claude_recommended_action": claude_result.recommended_action,
        "claude_alerts": claude_result.alerts,
        "claude_reasoning": claude_result.reasoning,
        "account_count": len(accounts),
        "transaction_count_analysed": len(recent_transactions),
    }

    # Audit log FIRST — mandatory before returning, even though treasury is read-only
    await write_audit_log(
        tenant_id=tenant_id,
        actor=_ACTOR,
        action=f"treasury:{overall_decision}",
        reasoning_trace=reasoning_trace,
        model_version=_MODEL_VERSION,
        execution_id=execution_id,
    )

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


async def run_treasury_job(
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
        result = await _execute_treasury(tenant_id, tool_id, execution_id)
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
                function_name="run_treasury_job",
                error=str(exc),
            )
        raise


# ---------------------------------------------------------------------------
# BaseTool class (orchestrator interface)
# ---------------------------------------------------------------------------


class TreasuryTool(BaseTool):
    TOOL_TYPE = ToolType.TREASURY
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> ToolOutput:
        execution_id: str = input_data["execution_id"]
        tool_id: str = input_data["tool_id"]

        result = await _execute_treasury(tenant_id, tool_id, execution_id)
        return ToolOutput(
            tool_type=self.TOOL_TYPE,
            decision=result["decision"],
            confidence=result["confidence"],
            reasoning=result["reasoning"],
            actions_taken=result["actions_taken"],
            output_data=result["output_data"],
        )
