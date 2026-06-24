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

_DAYS_30 = 30
_DAYS_90 = 90


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

class _ToolPolicy(BaseModel):
    min_balance_alert: int = 1000000          # pence — alert threshold
    cash_runway_warning_days: int = 90
    forecast_horizon_days: int = 30
    minimum_operating_balance_alert_days: int = 45
    critical_balance_alert_days: int = 14
    runway_alert_days: int = 90
    runway_critical_days: int = 30
    forecast_update_frequency: str = "weekly"
    forecast_method: str = "hybrid"
    cash_sweep_enabled: bool = False          # off by default — miscalibration risk
    cash_sweep_threshold: int = 50000000      # $500,000
    cash_sweep_retain_minimum: int = 10000000 # $100,000
    bank_counterparty_limit: int = 25000000   # $250,000 FDIC ceiling
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


class _BurnRate(BaseModel):
    daily_burn_30d: int          # average daily outflow in minor units over last 30 days
    daily_burn_90d: int          # average daily outflow in minor units over last 90 days
    runway_days_30d: int | None  # None when no outflow history
    runway_days_90d: int | None


class _ClaudeResult(BaseModel):
    total_balance_minor: int
    avg_daily_spend_minor: int
    forecast_runway_days: int
    alerts: list[str]
    recommended_action: Literal["monitor", "sweep", "alert_cfo", "emergency"]
    sweep_recommended: bool
    reasoning: str


# ---------------------------------------------------------------------------
# Policy parser
# ---------------------------------------------------------------------------

def _parse_policy(config_json: dict) -> _ToolPolicy:
    raw = config_json.get("policy", config_json)
    defaults = _ToolPolicy()
    filtered = {k: raw[k] for k in _ToolPolicy.model_fields if k in raw}
    return _ToolPolicy(**{**defaults.model_dump(), **filtered})


# ---------------------------------------------------------------------------
# Burn rate calculation (integer arithmetic only)
# ---------------------------------------------------------------------------

def _compute_burn_rate(
    transactions: list[_TransactionSummary],
    total_balance_minor: int,
    now: datetime,
) -> _BurnRate:
    def _outflows(cutoff: datetime) -> int:
        return sum(abs(t.amount_minor) for t in transactions if t.amount_minor < 0 and t.date >= cutoff)

    out30 = _outflows(now - timedelta(days=_DAYS_30))
    out90 = _outflows(now - timedelta(days=_DAYS_90))
    burn30: int = out30 // _DAYS_30
    burn90: int = out90 // _DAYS_90
    return _BurnRate(
        daily_burn_30d=burn30,
        daily_burn_90d=burn90,
        runway_days_30d=total_balance_minor // burn30 if burn30 > 0 else None,
        runway_days_90d=total_balance_minor // burn90 if burn90 > 0 else None,
    )


def _confidence_from_runway(runway_days_30d: int | None) -> float:
    if runway_days_30d is None:
        return 0.75  # no transaction history — cannot assess
    if runway_days_30d > 180:
        return 0.95
    if runway_days_30d > 90:
        return 0.80
    if runway_days_30d > 60:
        return 0.65
    return 0.50  # <= 60 days — low confidence, needs human review


# ---------------------------------------------------------------------------
# Claude prompt + call
# ---------------------------------------------------------------------------

def _build_claude_prompt(
    accounts: list[_AccountSummary],
    recent_transactions: list[_TransactionSummary],
    burn_rate: _BurnRate,
    policy: _ToolPolicy,
) -> str:
    accts = json.dumps([a.model_dump() for a in accounts], indent=2)
    txns = json.dumps(
        [{"id": t.id, "account_id": t.account_id, "amount_minor": t.amount_minor,
          "date": t.date.isoformat(), "description": t.description, "category": t.category}
         for t in recent_transactions],
        indent=2,
    )
    return (
        "You are a treasury analyst. Analyse accounts, transactions, and burn rates below.\n\n"
        f"Pre-computed burn rates (minor units):\n"
        f"  daily_burn_30d={burn_rate.daily_burn_30d}  daily_burn_90d={burn_rate.daily_burn_90d}\n"
        f"  runway_days_30d={burn_rate.runway_days_30d}  runway_days_90d={burn_rate.runway_days_90d}\n\n"
        "Tasks:\n"
        "1. Validate avg_daily_spend_minor from transactions (outflows only, negative amount_minor).\n"
        "2. Identify TOP 3 anomalous spend categories with totals in minor units.\n"
        "3. Recommend cash sweep if balance is high relative to needs — name target account.\n"
        "4. State whether a runway alert should fire and at what threshold.\n"
        "5. Choose recommended_action: monitor|sweep|alert_cfo|emergency.\n\n"
        "Return ONLY a JSON object with fields:\n"
        '  total_balance_minor, avg_daily_spend_minor, forecast_runway_days,\n'
        '  alerts (array — include top-3 anomalous categories as "<cat>: <amount> minor units"),\n'
        '  recommended_action ("monitor"|"sweep"|"alert_cfo"|"emergency"),\n'
        '  sweep_recommended (boolean), reasoning (one paragraph).\n\n'
        f"Accounts:\n{accts}\n\nTransactions (last {policy.forecast_horizon_days}d):\n{txns}"
    )


async def _call_claude(
    accounts: list[_AccountSummary],
    transactions: list[_TransactionSummary],
    burn_rate: _BurnRate,
    policy: _ToolPolicy,
    settings_obj,
) -> _ClaudeResult:
    client = AsyncAnthropic(api_key=settings_obj.anthropic_api_key)
    prompt = _build_claude_prompt(accounts, transactions, burn_rate, policy)
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
    now = datetime.now(UTC)

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

    # Fetch 90 days of transactions to cover both burn rate windows
    cutoff_90 = now - timedelta(days=_DAYS_90)
    raw_txns = await db.banktransaction.find_many(
        where={
            "tenant_id": tenant_id,
            "date": {"gte": cutoff_90},
        }
    )

    all_transactions = [
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

    # Compute burn rates before calling Claude
    burn_rate = _compute_burn_rate(all_transactions, total_balance_minor, now)

    # Subset for Claude context — only the configured forecast horizon
    cutoff_horizon = now - timedelta(days=policy.forecast_horizon_days)
    recent_transactions = [t for t in all_transactions if t.date >= cutoff_horizon]

    # Call Claude for runway forecast, anomaly detection, and action recommendation
    claude_result = await _call_claude(
        accounts, recent_transactions, burn_rate, policy, settings_obj
    )

    # Runway check using 30d burn rate (most current)
    runway_days_30d = burn_rate.runway_days_30d
    runway_alert: bool = (
        runway_days_30d is not None and runway_days_30d < policy.cash_runway_warning_days
    )

    # Derive overall decision
    critically_low = total_balance_minor < (policy.min_balance_alert // 2)
    critically_short_runway = (
        runway_days_30d is not None
        and runway_days_30d < (policy.cash_runway_warning_days // 2)
    )

    if alert_triggered or runway_alert or claude_result.alerts or critically_low or critically_short_runway:
        overall_decision = "approval_required"
    else:
        overall_decision = "auto_approved"

    confidence = _confidence_from_runway(burn_rate.runway_days_30d)

    actions_taken: list[str] = []
    if alert_triggered:
        actions_taken.append(
            f"balance_alert: total balance {total_balance_minor} minor units is below "
            f"threshold {policy.min_balance_alert}"
        )
    if runway_alert:
        actions_taken.append(
            f"runway_alert: 30d runway {runway_days_30d} days is below "
            f"warning threshold {policy.cash_runway_warning_days} days"
        )
    for alert in claude_result.alerts:
        actions_taken.append(f"pattern_alert: {alert}")
    if not actions_taken:
        actions_taken.append("cash position healthy — no alerts triggered")

    reasoning_trace: dict = {
        "overall_decision": overall_decision,
        "total_balance_minor": total_balance_minor,
        "burn_rate_daily_minor_30d": burn_rate.daily_burn_30d,
        "burn_rate_daily_minor_90d": burn_rate.daily_burn_90d,
        "runway_days_30d": burn_rate.runway_days_30d,
        "runway_days_90d": burn_rate.runway_days_90d,
        "avg_daily_spend_minor": claude_result.avg_daily_spend_minor,
        "forecast_runway_days": claude_result.forecast_runway_days,
        "alert_triggered": alert_triggered,
        "runway_alert": runway_alert,
        "recommended_action": claude_result.recommended_action,
        "sweep_recommended": claude_result.sweep_recommended,
        "policy": policy.model_dump(),
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
