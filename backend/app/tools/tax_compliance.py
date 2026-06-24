"""
Tax Compliance Tool — sub-agent tool. Called by Financial Orchestrator as a tool.
Calculates VAT liability, identifies missing-tax transactions, and alerts on threshold breaches.
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

_ACTOR = "tool:tax_compliance:v1"
_MODEL_VERSION = "tax_compliance-v1"
TOOL_TYPE = ToolType.TAX_COMPLIANCE

_LOOKBACK_DAYS = 90
_CLASSIFICATION_MISSING_VAT = "missing_vat"
_CLASSIFICATION_EXEMPT = "exempt"


class _ToolPolicy(BaseModel):
    vat_alert_threshold_cents: int = 1_000_000
    missing_tax_flag_threshold_cents: int = 10_000


def _parse_policy(config_json: dict) -> _ToolPolicy:
    raw = config_json.get("policy", config_json)
    return _ToolPolicy(**{k: v for k, v in raw.items() if k in _ToolPolicy.model_fields})


def _detect_filing_period(lookback_days: int, reference_date: datetime) -> tuple[str, str]:
    """Determine filing period and human-readable label from lookback window."""
    if lookback_days <= 31:
        return ("monthly", reference_date.strftime("%B %Y"))
    if lookback_days <= 92:
        quarter = (reference_date.month - 1) // 3 + 1
        return ("quarterly", f"Q{quarter} {reference_date.year}")
    return ("annual", str(reference_date.year))


def _flag_missing_tax(rows, threshold_cents: int, id_field: str = "id") -> list[dict]:
    """Return records where tax_cents == 0 and total > threshold."""
    flagged = []
    for r in rows:
        tax = getattr(r, "tax_cents", None) or 0
        total = getattr(r, "total_cents", None) or getattr(r, "amount_cents", None) or 0
        if tax == 0 and total >= threshold_cents:
            flagged.append({"id": getattr(r, id_field), "total_cents": total})
    return flagged


def _build_prompt(
    vat_collected: int,
    input_vat: int,
    net_vat: int,
    missing_invoice: list[dict],
    missing_bill: list[dict],
    missing_expense: list[dict],
    tax_rates: list[dict],
    policy: _ToolPolicy,
    filing_period: str,
    period_label: str,
) -> str:
    data = {
        "filing_period": filing_period, "period_label": period_label,
        "vat_collected_cents": vat_collected, "input_vat_reclaimable_cents": input_vat,
        "net_vat_liability_cents": net_vat, "missing_tax_invoices": missing_invoice,
        "missing_tax_bills": missing_bill, "missing_tax_expenses": missing_expense,
        "available_tax_rates": tax_rates, "vat_alert_threshold_cents": policy.vat_alert_threshold_cents,
    }
    return (
        "You are a tax compliance specialist. Analyse the VAT summary below and return a JSON object with "
        "exactly these fields:\n"
        '  "vat_position_assessment": string (1-2 sentences on the net VAT position),\n'
        '  "missing_tax_risk": "low"|"medium"|"high",\n'
        '  "vat_threshold_breached": boolean (true if net_vat_liability > vat_alert_threshold),\n'
        '  "likely_taxable_missing": array of strings — IDs of records most likely to require tax,\n'
        '  "recommended_actions": array of up to 3 action strings,\n'
        '  "classified_missing_items": array of objects, one per missing-tax record, each with:\n'
        '    { "id": string, "classification": "exempt"|"zero_rated"|"missing_vat"|"data_error", "reason": string }\n'
        "Classification rules:\n"
        '  "exempt" — correctly zero-rated (e.g. financial services, education, healthcare)\n'
        '  "zero_rated" — zero-rated supply (exports, certain food, children\'s clothing)\n'
        '  "missing_vat" — VAT should have been charged but was not — compliance risk\n'
        '  "data_error" — likely data entry error, not a genuine tax issue\n'
        "Return ONLY valid JSON. No markdown, no prose.\n\n"
        f"Data:\n{json.dumps(data, indent=2)}"
    )


async def _call_claude(
    vat_collected: int,
    input_vat: int,
    net_vat: int,
    missing_invoice: list[dict],
    missing_bill: list[dict],
    missing_expense: list[dict],
    tax_rates: list[dict],
    policy: _ToolPolicy,
    filing_period: str,
    period_label: str,
    settings_obj,
) -> dict:
    client = AsyncAnthropic(api_key=settings_obj.anthropic_api_key)
    prompt = _build_prompt(
        vat_collected, input_vat, net_vat,
        missing_invoice, missing_bill, missing_expense,
        tax_rates, policy, filing_period, period_label,
    )
    last_exc: Exception | None = None

    for attempt in range(settings_obj.max_agent_attempts):
        try:
            message = await client.messages.create(
                model=settings_obj.claude_model,
                max_tokens=1024,
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
    lookback_days: int = payload.get("lookback_days", _LOOKBACK_DAYS)
    now = datetime.now(UTC)
    lookback = now - timedelta(days=lookback_days)
    filing_period, period_label = _detect_filing_period(lookback_days, now)

    invoices, bills, expenses, tax_rates = await asyncio.gather(
        db.accountinginvoice.find_many(
            where={"tenant_id": tenant_id, "issue_date": {"gte": lookback}, "status": {"not": "draft"}}
        ),
        db.accountingbill.find_many(where={"tenant_id": tenant_id, "issue_date": {"gte": lookback}}),
        db.accountingexpense.find_many(where={"tenant_id": tenant_id, "issue_date": {"gte": lookback}}),
        db.accountingtaxrate.find_many(where={"tenant_id": tenant_id}),
    )

    if not invoices and not bills and not expenses:
        await write_audit_log(
            tenant_id=tenant_id, actor=_ACTOR, action="tax_compliance:no_action",
            reasoning_trace={"reason": "no_data_in_lookback_window"},
            model_version=_MODEL_VERSION, execution_id=execution_id,
        )
        return {
            "decision": "no_action", "confidence": 1.0,
            "reasoning": f"No transactions found in the last {lookback_days} days.",
            "actions_taken": [], "output_data": {},
        }

    vat_collected = sum(getattr(inv, "tax_cents", None) or 0 for inv in invoices)
    input_vat = sum((getattr(b, "tax_cents", None) or 0) for b in bills) + sum(
        (getattr(e, "tax_cents", None) or 0) for e in expenses
    )
    net_vat_liability_minor = vat_collected - input_vat

    missing_invoice = _flag_missing_tax(invoices, policy.missing_tax_flag_threshold_cents)
    missing_bill = _flag_missing_tax(bills, policy.missing_tax_flag_threshold_cents)
    missing_expense = _flag_missing_tax(expenses, policy.missing_tax_flag_threshold_cents)

    # Hard rules BEFORE calling Claude
    threshold_breached = net_vat_liability_minor > policy.vat_alert_threshold_cents
    total_missing_cents = sum(m["total_cents"] for m in missing_invoice + missing_bill + missing_expense)
    missing_over_threshold = total_missing_cents > policy.missing_tax_flag_threshold_cents

    tax_rate_list = [
        {"id": tr.id, "name": getattr(tr, "name", None), "rate": getattr(tr, "rate", None)}
        for tr in tax_rates
    ]

    claude_assessment = await _call_claude(
        vat_collected, input_vat, net_vat_liability_minor,
        missing_invoice, missing_bill, missing_expense,
        tax_rate_list, policy, filing_period, period_label, settings_obj,
    )

    classified_items: list[dict] = claude_assessment.get("classified_missing_items", [])
    missing_vat_count = sum(1 for item in classified_items if item.get("classification") == _CLASSIFICATION_MISSING_VAT)
    exempt_count = sum(1 for item in classified_items if item.get("classification") == _CLASSIFICATION_EXEMPT)

    # Final decision: hard rule threshold takes priority
    if threshold_breached:
        overall = "vat_alert"
    elif missing_over_threshold or missing_vat_count > 0:
        overall = "compliance_review"
    else:
        overall = "auto_approved"

    confidence = 0.85 if overall != "auto_approved" else 0.92

    reasoning_trace = {
        "overall_decision": overall, "filing_period": filing_period, "period_label": period_label,
        "vat_collected_cents": vat_collected, "input_vat_cents": input_vat,
        "net_vat_liability_minor": net_vat_liability_minor, "threshold_breached": threshold_breached,
        "missing_vat_items_count": missing_vat_count, "exempt_items_count": exempt_count,
        "missing_tax_count": {
            "invoices": len(missing_invoice), "bills": len(missing_bill), "expenses": len(missing_expense),
        },
        "missing_invoice_ids": [m["id"] for m in missing_invoice],
        "missing_bill_ids": [m["id"] for m in missing_bill],
        "missing_expense_ids": [m["id"] for m in missing_expense],
        "policy": policy.model_dump(), "claude_assessment": claude_assessment,
    }

    await write_audit_log(
        tenant_id=tenant_id, actor=_ACTOR, action=f"tax_compliance:{overall}",
        reasoning_trace=reasoning_trace, model_version=_MODEL_VERSION, execution_id=execution_id,
    )

    actions_taken = [
        f"analysed {len(invoices)} invoices, {len(bills)} bills, {len(expenses)} expenses",
        f"net VAT liability: {net_vat_liability_minor} cents ({period_label})",
    ]
    if threshold_breached:
        actions_taken.append(f"VAT ALERT: net liability {net_vat_liability_minor} exceeds threshold {policy.vat_alert_threshold_cents}")
    if missing_vat_count:
        actions_taken.append(f"flagged {missing_vat_count} transaction(s) with missing VAT")

    output_data = {
        **reasoning_trace,
        "net_vat_liability_minor": net_vat_liability_minor,
        "filing_period": filing_period, "period_label": period_label,
        "missing_vat_items_count": missing_vat_count, "exempt_items_count": exempt_count,
    }

    return {
        "decision": overall, "confidence": confidence,
        "reasoning": json.dumps(reasoning_trace),
        "actions_taken": actions_taken, "output_data": output_data,
    }


async def run_tax_compliance_job(
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
            data={"status": "completed", "decision": result["decision"],
                  "confidence": result["confidence"], "duration_ms": duration_ms},
        )
        if result["decision"] in ("vat_alert", "compliance_review"):
            await db.approval.create(data={
                "tenant_id": tenant_id, "execution_id": execution_id,
                "expires_at": datetime.now(UTC) + timedelta(seconds=settings_obj.approval_ttl_seconds),
            })
        return result
    except Exception as exc:
        try:
            await db.execution.update(where={"id": execution_id}, data={"status": "failed", "decision": "failed"})
        except Exception:
            pass
        if ctx.get("job_try", 1) >= 3:
            await push_to_dlq(job_id=str(ctx.get("job_id", "unknown")),
                               function_name="run_tax_compliance_job", error=str(exc))
        raise


class TaxComplianceTool(BaseTool):
    TOOL_TYPE = ToolType.TAX_COMPLIANCE
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> ToolOutput:
        result = await _execute(
            tenant_id, input_data["tool_id"], input_data["execution_id"], input_data.get("payload", {}),
        )
        return ToolOutput(
            tool_type=self.TOOL_TYPE, decision=result["decision"], confidence=result["confidence"],
            reasoning=result["reasoning"], actions_taken=result["actions_taken"],
            output_data=result["output_data"],
        )
