"""
Credit Underwriting Tool — sub-agent tool. Called by Financial Orchestrator as a tool.
Receives a credit application, applies hard decisioning rules, calls Claude for risk assessment,
and returns approve / refer / decline with full reasoning trace and audit log.
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

_ACTOR = "tool:credit_underwriting:v1"
_MODEL_VERSION = "credit_underwriting-v1"

EmploymentStatus = Literal["employed", "self_employed", "unemployed"]
ClaudeAssessment = Literal["approved", "referred", "declined"]
RiskGrade = Literal["A", "B", "C", "D", "E"]

# Interest rate bands in basis points per risk grade
RATE_BANDS_BPS: dict[str, tuple[int, int]] = {
    "A": (250, 400),    # 2.5% – 4.0%
    "B": (400, 600),    # 4.0% – 6.0%
    "C": (600, 900),    # 6.0% – 9.0%
    "D": (900, 1400),   # 9.0% – 14.0%
    "E": (1400, 2400),  # 14.0% – 24.0%
}


class _ApplicationInput(BaseModel):
    application_id: str
    applicant_name: str
    requested_amount_minor: int
    currency: str
    credit_score: int
    declared_income_minor: int           # monthly income in minor units
    monthly_debt_payments_minor: int     # existing monthly debt obligations
    proposed_monthly_payment_minor: int = 0  # new payment being applied for
    monthly_housing_payment_minor: int = 0   # for front-end DTI (optional)
    employment_status: EmploymentStatus
    employment_months: int
    bank_transactions_summary: str
    collateral_value_minor: int = 0      # for LTV check on secured loans


class _ToolPolicy(BaseModel):
    min_credit_score: int = 650
    max_dti_ratio: float = 0.43
    auto_approve_score_min: int = 720
    manual_review_score_min: int = 620
    max_ltv_ratio: float = 0.80
    min_employment_months: int = 6
    min_annual_income: int = 2000000
    max_loan_amount: int = 50000000
    min_loan_amount: int = 100000
    max_term_months: int = 84
    max_open_derogatory_marks: int = 0
    bankruptcy_lookback_years: int = 7
    fraud_check_enabled: bool = True
    income_verification_required_above: int = 5000000
    adverse_action_notice_auto: bool = True  # ECOA legal requirement


class _ClaudeRiskResult(BaseModel):
    risk_assessment: ClaudeAssessment
    risk_grade: RiskGrade
    risk_factors: list[str]
    mitigating_factors: list[str]
    approved_amount_minor: int | None
    interest_rate_bps: int | None
    conditions: list[str]
    confidence: float
    reasoning: str


def _parse_policy(config_json: dict) -> _ToolPolicy:
    raw = config_json.get("policy", config_json)
    return _ToolPolicy(**{k: v for k, v in raw.items() if k in _ToolPolicy.model_fields})


def _calculate_dti(application: _ApplicationInput) -> tuple[float | None, float]:
    """Return (front_end_dti, back_end_dti). front_end_dti is None if no housing payment provided."""
    income = application.declared_income_minor
    if income <= 0:
        return (None, float("inf"))
    front_end = application.monthly_housing_payment_minor / income if application.monthly_housing_payment_minor > 0 else None
    back_end = (application.monthly_debt_payments_minor + application.proposed_monthly_payment_minor) / income
    return (front_end, back_end)


def _clamp_rate_to_band(grade: RiskGrade, rate_bps: int | None) -> tuple[int | None, bool]:
    """Clamp interest_rate_bps to the grade's band. Returns (clamped_rate, was_clamped)."""
    if rate_bps is None:
        return (None, False)
    low, high = RATE_BANDS_BPS[grade]
    clamped = max(low, min(high, rate_bps))
    return (clamped, clamped != rate_bps)


def _build_adverse_action_notice(reasons: list[str]) -> dict:
    """Generate ECOA §202.9-compliant adverse action notice."""
    return {"reasons": reasons[:4], "notice_required": True, "deadline_days": 30}


def _build_claude_prompt(
    application: _ApplicationInput,
    front_end_dti: float | None,
    back_end_dti: float,
) -> str:
    payload = json.dumps({
        "application_id": application.application_id,
        "requested_amount_minor": application.requested_amount_minor,
        "currency": application.currency,
        "credit_score": application.credit_score,
        "declared_income_minor": application.declared_income_minor,
        "monthly_debt_payments_minor": application.monthly_debt_payments_minor,
        "proposed_monthly_payment_minor": application.proposed_monthly_payment_minor,
        "front_end_dti": round(front_end_dti, 4) if front_end_dti is not None else None,
        "back_end_dti": round(back_end_dti, 4),
        "employment_status": application.employment_status,
        "employment_months": application.employment_months,
        "bank_transactions_summary": application.bank_transactions_summary,
    }, indent=2)
    return (
        "You are a credit risk assessment model. Analyse the credit application below and "
        "return ONLY a valid JSON object with exactly these fields:\n"
        '  "risk_assessment": one of "approved" | "referred" | "declined",\n'
        '  "risk_grade": one of "A" | "B" | "C" | "D" | "E" (A = lowest risk),\n'
        '  "risk_factors": array of up to 3 negative risk factor strings,\n'
        '  "mitigating_factors": array of positive signals from the application (empty array if none),\n'
        '  "approved_amount_minor": integer in minor currency units or null if not approved,\n'
        '  "interest_rate_bps": integer basis points (e.g. 450 = 4.50%) or null if not approved,\n'
        '  "conditions": array of specific actionable conditions the applicant must meet for approval (empty array if none),\n'
        '  "confidence": float 0.0–1.0 (your confidence in this assessment),\n'
        '  "reasoning": detailed reasoning string.\n\n'
        "Rules:\n"
        "- Grade A–B with credit_score >= 700 and back_end_dti <= 0.3 → lean toward approved\n"
        "- Grade C–D with credit_score 650–699 or back_end_dti 0.3–0.43 → lean toward referred\n"
        "- Grade E or credit instability in bank transactions → lean toward declined\n"
        "- Consider income stability, spending patterns, and employment duration\n"
        "- approved_amount_minor must not exceed requested_amount_minor\n"
        "- interest_rate_bps must reflect the risk grade: A=250-400, B=400-600, C=600-900, D=900-1400, E=1400-2400\n"
        "- conditions must be specific and actionable (e.g. 'Provide 3 months of pay stubs')\n"
        "Return ONLY the JSON object. No markdown, no explanation outside the JSON.\n\n"
        f"Application:\n{payload}"
    )


async def _call_claude(
    application: _ApplicationInput,
    front_end_dti: float | None,
    back_end_dti: float,
) -> _ClaudeRiskResult:
    settings_obj = get_settings()
    client = AsyncAnthropic(api_key=settings_obj.anthropic_api_key)
    prompt = _build_claude_prompt(application, front_end_dti, back_end_dti)
    last_exc: Exception | None = None

    for attempt in range(settings_obj.max_agent_attempts):
        try:
            message = await client.messages.create(
                model=settings_obj.claude_model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            return _ClaudeRiskResult(**json.loads(message.content[0].text.strip()))
        except (APIStatusError, APIConnectionError) as exc:
            last_exc = exc
            logger.error("claude_api_error", extra={"attempt": attempt + 1, "error": str(exc)})
            if attempt < settings_obj.max_agent_attempts - 1:
                await asyncio.sleep(settings_obj.backoff_seconds * (attempt + 1))
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            raise RuntimeError(f"Claude returned unparseable response: {exc}") from exc

    raise RuntimeError(f"Claude API failed after {settings_obj.max_agent_attempts} attempts: {last_exc}")


def _apply_hard_rules(
    application: _ApplicationInput,
    policy: _ToolPolicy,
    back_end_dti: float,
) -> tuple[str, str, list[str]] | None:
    """Returns (decision, reason, ecoa_reasons) if a hard rule fires, otherwise None."""
    if application.credit_score < policy.min_credit_score:
        return ("blocked", "Credit score below minimum", ["Credit score below minimum"])
    if back_end_dti > policy.max_dti_ratio:
        return ("blocked", "Back-end DTI ratio exceeds maximum", ["Debt-to-income ratio too high"])
    if application.employment_status == "unemployed":
        return ("blocked", "Applicant is unemployed", ["Insufficient employment history"])
    if (
        application.collateral_value_minor > 0
        and application.requested_amount_minor > 0
        and (application.requested_amount_minor / application.collateral_value_minor) > policy.max_ltv_ratio
    ):
        return ("blocked", "Loan-to-value ratio exceeds maximum", ["Loan-to-value ratio exceeds maximum"])
    return None


def _map_claude_decision(risk_assessment: ClaudeAssessment) -> str:
    return {"approved": "auto_approved", "referred": "approval_required", "declined": "blocked"}[risk_assessment]


async def _execute_credit_underwriting(
    tenant_id: str,
    tool_id: str,
    execution_id: str,
    application_data: dict,
) -> dict:
    db = get_db()
    tool = await db.tool.find_first(where={"id": tool_id, "tenant_id": tenant_id})
    if tool is None:
        raise ValueError(f"Tool {tool_id} not found for tenant {tenant_id}")

    policy = _parse_policy(tool.config_json if isinstance(tool.config_json, dict) else {})
    application = _ApplicationInput(**application_data)
    front_end_dti, back_end_dti = _calculate_dti(application)
    hard_rule_result = _apply_hard_rules(application, policy, back_end_dti)

    def _fmt_dti(v: float | None) -> float | None:
        return round(v, 4) if v is not None else None

    if hard_rule_result is not None:
        decision, hard_rule_reason, ecoa_reasons = hard_rule_result
        reasoning_trace: dict = {
            "application_id": application.application_id,
            "credit_score": application.credit_score,
            "front_end_dti": _fmt_dti(front_end_dti),
            "back_end_dti": round(back_end_dti, 4),
            "hard_rule_triggered": hard_rule_reason,
            "claude_assessment": None,
            "decision": decision,
        }
        await write_audit_log(
            tenant_id=tenant_id, actor=_ACTOR,
            action=f"credit_underwriting:{decision}",
            reasoning_trace=reasoning_trace, model_version=_MODEL_VERSION, execution_id=execution_id,
        )
        return {
            "decision": decision, "confidence": 1.0, "reasoning": hard_rule_reason,
            "actions_taken": [f"hard_rule_blocked: {hard_rule_reason}"],
            "output_data": {
                "application_id": application.application_id, "decision": decision,
                "hard_rule_triggered": hard_rule_reason, "credit_score": application.credit_score,
                "front_end_dti": _fmt_dti(front_end_dti), "back_end_dti": round(back_end_dti, 4),
                "risk_grade": None, "risk_factors": [hard_rule_reason], "mitigating_factors": [],
                "approved_amount_minor": None, "interest_rate_bps": None, "conditions": [],
                "confidence": 1.0, "reasoning": hard_rule_reason,
                "adverse_action_notice": _build_adverse_action_notice(ecoa_reasons),
            },
        }

    claude_result = await _call_claude(application, front_end_dti, back_end_dti)
    decision = _map_claude_decision(claude_result.risk_assessment)

    clamped_rate, was_clamped = _clamp_rate_to_band(claude_result.risk_grade, claude_result.interest_rate_bps)
    if was_clamped:
        logger.warning("interest_rate_clamped_to_band", extra={
            "application_id": application.application_id, "grade": claude_result.risk_grade,
            "original_bps": claude_result.interest_rate_bps, "clamped_bps": clamped_rate,
            "band": RATE_BANDS_BPS[claude_result.risk_grade],
        })

    adverse_action_notice = None
    if decision == "blocked" and policy.adverse_action_notice_auto:
        ecoa_reasons = claude_result.risk_factors[:4] or ["Credit application declined"]
        adverse_action_notice = _build_adverse_action_notice(ecoa_reasons)

    reasoning_trace = {
        "application_id": application.application_id, "credit_score": application.credit_score,
        "front_end_dti": _fmt_dti(front_end_dti), "back_end_dti": round(back_end_dti, 4),
        "hard_rule_triggered": None,
        "claude_assessment": {
            "risk_assessment": claude_result.risk_assessment, "risk_grade": claude_result.risk_grade,
            "risk_factors": claude_result.risk_factors, "mitigating_factors": claude_result.mitigating_factors,
            "approved_amount_minor": claude_result.approved_amount_minor, "interest_rate_bps": clamped_rate,
            "conditions": claude_result.conditions, "confidence": claude_result.confidence,
            "reasoning": claude_result.reasoning,
        },
        "decision": decision, "rate_clamped": was_clamped,
    }

    # Audit log BEFORE returning — operation fails if audit fails
    await write_audit_log(
        tenant_id=tenant_id, actor=_ACTOR,
        action=f"credit_underwriting:{decision}",
        reasoning_trace=reasoning_trace, model_version=_MODEL_VERSION, execution_id=execution_id,
    )

    actions_taken: list[str] = [f"credit_assessed: grade={claude_result.risk_grade}, decision={decision}"]
    if was_clamped:
        actions_taken.append(
            f"rate_clamped: {claude_result.interest_rate_bps}bps → {clamped_rate}bps "
            f"(band {RATE_BANDS_BPS[claude_result.risk_grade]})"
        )

    return {
        "decision": decision, "confidence": claude_result.confidence, "reasoning": claude_result.reasoning,
        "actions_taken": actions_taken,
        "output_data": {
            "application_id": application.application_id, "decision": decision,
            "hard_rule_triggered": None, "credit_score": application.credit_score,
            "front_end_dti": _fmt_dti(front_end_dti), "back_end_dti": round(back_end_dti, 4),
            "risk_grade": claude_result.risk_grade, "risk_factors": claude_result.risk_factors,
            "mitigating_factors": claude_result.mitigating_factors,
            "approved_amount_minor": claude_result.approved_amount_minor, "interest_rate_bps": clamped_rate,
            "conditions": claude_result.conditions, "confidence": claude_result.confidence,
            "reasoning": claude_result.reasoning, "adverse_action_notice": adverse_action_notice,
        },
    }


async def run_credit_underwriting_job(
    ctx: dict,
    *,
    execution_id: str,
    tenant_id: str,
    tool_id: str,
    application_data: dict,
) -> dict:
    db = get_db()
    start_ms = int(time.time() * 1000)
    try:
        result = await _execute_credit_underwriting(tenant_id, tool_id, execution_id, application_data)
        duration_ms = int(time.time() * 1000) - start_ms
        await db.execution.update(
            where={"id": execution_id},
            data={"status": "completed", "decision": result["decision"],
                  "confidence": result["confidence"], "duration_ms": duration_ms},
        )
        if result["decision"] == "approval_required":
            settings_obj = get_settings()
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
                               function_name="run_credit_underwriting_job", error=str(exc))
        raise


class CreditUnderwritingTool(BaseTool):
    TOOL_TYPE = ToolType.CREDIT_UNDERWRITING
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> ToolOutput:
        result = await _execute_credit_underwriting(
            tenant_id, input_data["tool_id"], input_data["execution_id"], input_data["application_data"]
        )
        return ToolOutput(
            tool_type=self.TOOL_TYPE, decision=result["decision"], confidence=result["confidence"],
            reasoning=result["reasoning"], actions_taken=result["actions_taken"],
            output_data=result["output_data"],
        )
