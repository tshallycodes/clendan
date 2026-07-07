"""
Financial Reporting Tool — sub-agent tool. Dispatched directly to its arq job.
Aggregates accounting data to produce P&L, balance sheet, and cash flow summaries.
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
from app.core.execution import complete_execution
from app.core.logging import get_logger
from app.queue.pool import push_to_dlq
from app.tools.base import BaseTool, ToolOutput, ToolType

logger = get_logger(__name__)

_ACTOR = "tool:financial_reporting:v1"
_MODEL_VERSION = "financial_reporting-v1"
TOOL_TYPE = ToolType.FINANCIAL_REPORTING

# Canonical payment_type values written by the accounting sync layer
# (Xero / QuickBooks / FreshBooks — see app/integrations/*/persist.py).
# Inflows = money received from customers; outflows = money paid to suppliers.
_INFLOW_PAYMENT_TYPES = frozenset({"received"})
_OUTFLOW_PAYMENT_TYPES = frozenset({"made"})


class _ToolPolicy(BaseModel):
    lookback_days: int = 30
    anomaly_variance_pct: float = 0.25


def _parse_policy(config_json: dict) -> _ToolPolicy:
    raw = config_json.get("policy", config_json)
    return _ToolPolicy(
        lookback_days=raw.get("lookback_days", 30),
        anomaly_variance_pct=raw.get("anomaly_variance_pct", 0.25),
    )


class _FinancialSnapshot(BaseModel):
    period_start: str
    period_end: str
    revenue_cents: int
    outstanding_ar_cents: int
    cogs_cents: int
    opex_cents: int
    outstanding_ap_cents: int
    gross_profit_cents: int
    net_profit_cents: int
    total_bank_balance_cents: int
    total_assets_cents: int
    total_liabilities_cents: int
    net_assets_cents: int
    cash_inflows_cents: int
    cash_outflows_cents: int
    net_cash_cents: int
    invoice_count: int
    bill_count: int
    expense_count: int


def _build_snapshot(invoices, bills, expenses, payments, bank_accounts, p_start: datetime, p_end: datetime) -> _FinancialSnapshot:
    def in_period(dt) -> bool:
        if dt is None:
            return False
        d = dt if isinstance(dt, datetime) else datetime(dt.year, dt.month, dt.day, tzinfo=UTC)
        return p_start <= d <= p_end

    revenue_cents = sum(inv.total_cents for inv in invoices if in_period(inv.issue_date))
    outstanding_ar_cents = sum(inv.outstanding_cents for inv in invoices if inv.outstanding_cents > 0)
    bill_total_cents = sum(b.total_cents for b in bills if in_period(b.issue_date))
    outstanding_ap_cents = sum(b.outstanding_cents for b in bills if b.outstanding_cents > 0)
    opex_cents = sum(e.amount_cents for e in expenses if in_period(e.expense_date))
    cogs_cents = bill_total_cents
    gross_profit_cents = revenue_cents - cogs_cents
    net_profit_cents = gross_profit_cents - opex_cents
    total_bank_balance_cents = sum(acc.current_balance_minor for acc in bank_accounts)
    total_assets_cents = total_bank_balance_cents + outstanding_ar_cents
    total_liabilities_cents = outstanding_ap_cents
    cash_inflows_cents = sum(p.amount_cents for p in payments if p.payment_type in _INFLOW_PAYMENT_TYPES and in_period(p.paid_at))
    cash_outflows_cents = sum(p.amount_cents for p in payments if p.payment_type in _OUTFLOW_PAYMENT_TYPES and in_period(p.paid_at))
    return _FinancialSnapshot(
        period_start=p_start.date().isoformat(), period_end=p_end.date().isoformat(),
        revenue_cents=revenue_cents, outstanding_ar_cents=outstanding_ar_cents,
        cogs_cents=cogs_cents, opex_cents=opex_cents, outstanding_ap_cents=outstanding_ap_cents,
        gross_profit_cents=gross_profit_cents, net_profit_cents=net_profit_cents,
        total_bank_balance_cents=total_bank_balance_cents,
        total_assets_cents=total_assets_cents, total_liabilities_cents=total_liabilities_cents,
        net_assets_cents=total_assets_cents - total_liabilities_cents,
        cash_inflows_cents=cash_inflows_cents, cash_outflows_cents=cash_outflows_cents,
        net_cash_cents=cash_inflows_cents - cash_outflows_cents,
        invoice_count=len(invoices), bill_count=len(bills), expense_count=len(expenses),
    )


def _compute_ratios(s: _FinancialSnapshot) -> dict:
    rev = s.revenue_cents
    return {
        "gross_margin_pct": round((rev - s.cogs_cents) / rev * 100, 2) if rev > 0 else 0,
        "net_margin_pct": round(s.net_profit_cents / rev * 100, 2) if rev > 0 else 0,
        "current_ratio": round(s.total_bank_balance_cents / s.outstanding_ap_cents, 4) if s.outstanding_ap_cents > 0 else None,
    }


def _compute_period_changes(cur: _FinancialSnapshot, prior: _FinancialSnapshot) -> dict:
    def pct(c: int, p: int) -> float | None:
        return round((c - p) / abs(p) * 100, 2) if p != 0 else None

    return {
        "prior_period_revenue_minor": prior.revenue_cents,
        "prior_period_expenses_minor": prior.cogs_cents + prior.opex_cents,
        "revenue_change_pct": pct(cur.revenue_cents, prior.revenue_cents),
        "expense_change_pct": pct(cur.cogs_cents + cur.opex_cents, prior.cogs_cents + prior.opex_cents),
        "net_income_change_pct": pct(cur.net_profit_cents, prior.net_profit_cents),
    }


def _compute_confidence(s: _FinancialSnapshot, has_anomaly: bool) -> float:
    data_complete = s.invoice_count > 0 and s.bill_count > 0 and s.expense_count > 0 and s.total_bank_balance_cents >= 0
    if data_complete and not has_anomaly:
        return 0.95
    return 0.88 if data_complete else 0.75


def _build_prompt(snapshot: _FinancialSnapshot, policy: _ToolPolicy, ratios: dict, period_changes: dict) -> str:
    data = {**snapshot.model_dump(), **ratios, **period_changes}
    av = int(policy.anomaly_variance_pct * 100)
    return (
        "You are a CFO-level financial analyst. Analyse the financial snapshot below and return a JSON object "
        "with exactly these fields:\n"
        '  "pl_summary": string (3-4 sentences),\n'
        '  "balance_sheet_summary": string (2-3 sentences),\n'
        '  "cash_flow_summary": string (2-3 sentences),\n'
        '  "anomalies": array of strings (each: line item name, amount in cents, % deviation — top 3 max),\n'
        '  "has_anomaly": boolean,\n'
        '  "health_status": "healthy"|"watch"|"concerning"|"critical",\n'
        '  "top_recommendation": string (specific, actionable — not generic),\n'
        '  "overall_health": "strong"|"stable"|"at_risk",\n'
        '  "recommendations": array of up to 3 action strings\n\n'
        f"Flag anomalies: gross margin < 0, net profit negative, AP > AR by >20%, any figure varies >{av}% vs prior period.\n"
        "Return ONLY valid JSON. No markdown, no prose.\n\n"
        f"Financial snapshot:\n{json.dumps(data, indent=2)}"
    )


async def _call_claude(snapshot: _FinancialSnapshot, policy: _ToolPolicy, ratios: dict, period_changes: dict, settings_obj) -> dict:
    client = AsyncAnthropic(api_key=settings_obj.anthropic_api_key)
    prompt = _build_prompt(snapshot, policy, ratios, period_changes)
    last_exc: Exception | None = None
    for attempt in range(settings_obj.max_agent_attempts):
        try:
            msg = await client.messages.create(model=settings_obj.claude_model, max_tokens=1024, messages=[{"role": "user", "content": prompt}])
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
    period_end = datetime.now(UTC)
    period_start = period_end - timedelta(days=policy.lookback_days)
    prior_end = period_start
    prior_start = prior_end - timedelta(days=policy.lookback_days)

    invoices, bills, expenses, payments, bank_accounts = await asyncio.gather(
        db.accountinginvoice.find_many(where={"tenant_id": tenant_id}),
        db.accountingbill.find_many(where={"tenant_id": tenant_id}),
        db.accountingexpense.find_many(where={"tenant_id": tenant_id}),
        db.accountingpayment.find_many(where={"tenant_id": tenant_id}),
        db.bankaccount.find_many(where={"tenant_id": tenant_id}),
    )

    if not invoices and not bills and not expenses:
        await write_audit_log(tenant_id=tenant_id, actor=_ACTOR, action="financial_reporting:no_data",
                              reasoning_trace={"reason": "no_accounting_data"}, model_version=_MODEL_VERSION, execution_id=execution_id)
        return {"decision": "no_action", "confidence": 1.0, "reasoning": "No accounting data available.", "actions_taken": [], "output_data": {}}

    snapshot = _build_snapshot(invoices, bills, expenses, payments, bank_accounts, period_start, period_end)
    prior = _build_snapshot(invoices, bills, expenses, payments, bank_accounts, prior_start, prior_end)

    ratios = _compute_ratios(snapshot)
    period_changes = _compute_period_changes(snapshot, prior)

    threshold = policy.anomaly_variance_pct * 100
    period_anomalies = [
        f"{k} deviated {v:+.1f}% vs prior period (threshold ±{threshold:.0f}%)"
        for k in ("revenue_change_pct", "expense_change_pct", "net_income_change_pct")
        if (v := period_changes.get(k)) is not None and abs(v) > threshold
    ]

    claude_result = await _call_claude(snapshot, policy, ratios, period_changes, settings_obj)
    has_anomaly: bool = claude_result.get("has_anomaly", False) or bool(period_anomalies)

    if period_anomalies:
        claude_result["anomalies"] = claude_result.get("anomalies", []) + period_anomalies
        claude_result["has_anomaly"] = True

    overall = "approval_required" if (has_anomaly or claude_result.get("overall_health") == "at_risk") else "auto_approved"
    confidence = _compute_confidence(snapshot, has_anomaly)

    output_data = {
        **snapshot.model_dump(), **ratios, **period_changes,
        "health_status": claude_result.get("health_status", "watch"),
        "top_recommendation": claude_result.get("top_recommendation", ""),
        "period_anomalies": period_anomalies,
        "claude_result": claude_result,
        "policy": policy.model_dump(),
    }
    reasoning_trace = {"overall_decision": overall, "period_start": snapshot.period_start, "period_end": snapshot.period_end, **output_data}

    await write_audit_log(tenant_id=tenant_id, actor=_ACTOR, action=f"financial_reporting:{overall}",
                          reasoning_trace=reasoning_trace, model_version=_MODEL_VERSION, execution_id=execution_id)

    actions_taken = [
        f"generated report for {snapshot.period_start} to {snapshot.period_end}",
        f"analysed {snapshot.invoice_count} invoices, {snapshot.bill_count} bills, {snapshot.expense_count} expenses",
        f"computed ratios: gross_margin={ratios['gross_margin_pct']}%, net_margin={ratios['net_margin_pct']}%, current_ratio={ratios['current_ratio']}",
    ]
    if has_anomaly:
        actions_taken.append(f"flagged {len(claude_result.get('anomalies', []))} anomaly(ies)")

    return {"decision": overall, "confidence": confidence, "reasoning": json.dumps(reasoning_trace), "actions_taken": actions_taken, "output_data": output_data}


async def run_financial_reporting_job(ctx: dict, *, execution_id: str, tenant_id: str, tool_id: str, payload: dict, policy_config: dict) -> dict:
    db = get_db()
    start_ms = int(time.time() * 1000)
    try:
        result = await _execute(tenant_id, tool_id, execution_id, payload)
        duration_ms = int(time.time() * 1000) - start_ms
        await complete_execution(
            db=db, execution_id=execution_id, tool_id=tool_id,
            tenant_id=tenant_id, decision=result["decision"],
            confidence=result["confidence"], duration_ms=duration_ms,
        )
        return result
    except Exception as exc:
        try:
            await db.execution.update(where={"id": execution_id}, data={"status": "failed", "decision": "failed"})
        except Exception:
            pass
        if ctx.get("job_try", 1) >= 3:
            await push_to_dlq(job_id=str(ctx.get("job_id", "unknown")), function_name="run_financial_reporting_job", error=str(exc))
        raise


class FinancialReportingTool(BaseTool):
    TOOL_TYPE = ToolType.FINANCIAL_REPORTING
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> ToolOutput:
        result = await _execute(tenant_id, input_data["tool_id"], input_data["execution_id"], input_data.get("payload", {}))
        return ToolOutput(
            tool_type=self.TOOL_TYPE, decision=result["decision"], confidence=result["confidence"],
            reasoning=result["reasoning"], actions_taken=result["actions_taken"], output_data=result["output_data"],
        )
