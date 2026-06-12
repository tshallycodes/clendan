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


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class _ApplicationInput(BaseModel):
    application_id: str
    applicant_name: str
    requested_amount_minor: int
    currency: str
    credit_score: int
    declared_income_minor: int
    monthly_debt_payments_minor: int
    employment_status: EmploymentStatus
    employment_months: int
    bank_transactions_summary: str


class _ToolPolicy(BaseModel):
    min_credit_score: int = 650
    max_dti_ratio: float = 0.43
    auto_approve_score_min: int = 720
    manual_review_score_min: int = 620
    max_ltv_ratio: float = 0.80
    min_employment_months: int = 6
    min_annual_income: int = 2000000              # minor units ($20,000)
    max_loan_amount: int = 50000000               # minor units ($500,000)
    min_loan_amount: int = 100000                 # minor units ($1,000)
    max_term_months: int = 84
    max_open_derogatory_marks: int = 0
    bankruptcy_lookback_years: int = 7
    fraud_check_enabled: bool = True
    income_verification_required_above: int = 5000000  # minor units ($50,000)
    adverse_action_notice_auto: bool = True       # ECOA legal requirement


class _ClaudeRiskResult(BaseModel):
    risk_assessment: ClaudeAssessment
    risk_grade: RiskGrade
    risk_factors: list[str]
    approved_amount_minor: int | None
    interest_rate_bps: int | None
    conditions: list[str]
    confidence: float
    reasoning: str


# ---------------------------------------------------------------------------
# Policy helpers
# ---------------------------------------------------------------------------


def _parse_policy(config_json: dict) -> _ToolPolicy:
    raw = config_json.get("policy", config_json)
    return _ToolPolicy(
        min_credit_score=raw.get("min_credit_score", 650),
        max_dti_ratio=raw.get("max_dti_ratio", 0.43),
        auto_approve_score_min=raw.get("auto_approve_score_min", 720),
        manual_review_score_min=raw.get("manual_review_score_min", 620),
        max_ltv_ratio=raw.get("max_ltv_ratio", 0.80),
        min_employment_months=raw.get("min_employment_months", 6),
        min_annual_income=raw.get("min_annual_income", 2000000),
        max_loan_amount=raw.get("max_loan_amount", 50000000),
        min_loan_amount=raw.get("min_loan_amount", 100000),
        max_term_months=raw.get("max_term_months", 84),
        max_open_derogatory_marks=raw.get("max_open_derogatory_marks", 0),
        bankruptcy_lookback_years=raw.get("bankruptcy_lookback_years", 7),
        fraud_check_enabled=raw.get("fraud_check_enabled", True),
        income_verification_required_above=raw.get("income_verification_required_above", 5000000),
        adverse_action_notice_auto=raw.get("adverse_action_notice_auto", True),
    )


def _calculate_dti(monthly_debt_payments_minor: int, declared_income_minor: int) -> float:
    if declared_income_minor <= 0:
        return float("inf")
    return monthly_debt_payments_minor / declared_income_minor


# ---------------------------------------------------------------------------
# Claude prompt and call
# ---------------------------------------------------------------------------


def _build_claude_prompt(application: _ApplicationInput, dti_ratio: float) -> str:
    payload = json.dumps(
        {
            "application_id": application.application_id,
            "requested_amount_minor": application.requested_amount_minor,
            "currency": application.currency,
            "credit_score": application.credit_score,
            "declared_income_minor": application.declared_income_minor,
            "monthly_debt_payments_minor": application.monthly_debt_payments_minor,
            "dti_ratio": round(dti_ratio, 4),
            "employment_status": application.employment_status,
            "employment_months": application.employment_months,
            "bank_transactions_summary": application.bank_transactions_summary,
        },
        indent=2,
    )
    return (
        "You are a credit risk assessment model. Analyse the credit application below and "
        "return ONLY a valid JSON object with exactly these fields:\n"
        '  "risk_assessment": one of "approved" | "referred" | "declined",\n'
        '  "risk_grade": one of "A" | "B" | "C" | "D" | "E" (A = lowest risk),\n'
        '  "risk_factors": array of concise risk factor strings,\n'
        '  "approved_amount_minor": integer in minor currency units or null if not approved,\n'
        '  "interest_rate_bps": integer basis points (e.g. 450 = 4.50%) or null if not approved,\n'
        '  "conditions": array of condition strings (empty array if none),\n'
        '  "confidence": float 0.0–1.0 (your confidence in this assessment),\n'
        '  "reasoning": detailed reasoning string.\n\n'
        "Rules:\n"
        "- Grade A–B with credit_score >= 700 and dti_ratio <= 0.3 → lean toward approved\n"
        "- Grade C–D with credit_score 650–699 or dti_ratio 0.3–0.43 → lean toward referred\n"
        "- Grade E or credit instability in bank transactions → lean toward declined\n"
        "- Consider income stability, spending patterns, and employment duration\n"
        "- approved_amount_minor must not exceed requested_amount_minor\n"
        "Return ONLY the JSON object. No markdown, no explanation outside the JSON.\n\n"
        f"Application:\n{payload}"
    )


async def _call_claude(application: _ApplicationInput, dti_ratio: float) -> _ClaudeRiskResult:
    settings_obj = get_settings()
    client = AsyncAnthropic(api_key=settings_obj.anthropic_api_key)
    prompt = _build_claude_prompt(application, dti_ratio)
    last_exc: Exception | None = None

    for attempt in range(settings_obj.max_agent_attempts):
        try:
            message = await client.messages.create(
                model=settings_obj.claude_model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = message.content[0].text.strip()
            data = json.loads(raw_text)
            return _ClaudeRiskResult(**data)
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
# Hard-rule decisioning
# ---------------------------------------------------------------------------


def _apply_hard_rules(
    application: _ApplicationInput,
    policy: _ToolPolicy,
    dti_ratio: float,
) -> tuple[str, str] | None:
    """
    Apply hard decisioning rules in priority order.
    Returns (decision, reason) if a hard rule fires, otherwise None.
    """
    if application.credit_score < policy.min_credit_score:
        return ("blocked", "Credit score below minimum")

    if dti_ratio > policy.max_dti_ratio:
        return ("blocked", "DTI ratio exceeds maximum")

    if application.employment_status == "unemployed":
        return ("blocked", "Applicant is unemployed")

    return None


def _map_claude_decision(risk_assessment: ClaudeAssessment) -> str:
    mapping: dict[ClaudeAssessment, str] = {
        "approved": "auto_approved",
        "referred": "approval_required",
        "declined": "blocked",
    }
    return mapping[risk_assessment]


# ---------------------------------------------------------------------------
# Core execution
# ---------------------------------------------------------------------------


async def _execute_credit_underwriting(
    tenant_id: str,
    tool_id: str,
    execution_id: str,
    application_data: dict,
) -> dict:
    db = get_db()

    # Fetch and validate tool config
    tool = await db.tool.find_first(
        where={"id": tool_id, "tenant_id": tenant_id}
    )
    if tool is None:
        raise ValueError(f"Tool {tool_id} not found for tenant {tenant_id}")

    config_raw: dict = tool.config_json if isinstance(tool.config_json, dict) else {}
    policy = _parse_policy(config_raw)

    # Validate application input
    application = _ApplicationInput(**application_data)

    # Calculate DTI (float division — this is a ratio, not a money amount)
    dti_ratio = _calculate_dti(
        application.monthly_debt_payments_minor,
        application.declared_income_minor,
    )

    # Apply hard rules before calling Claude
    hard_rule_result = _apply_hard_rules(application, policy, dti_ratio)

    if hard_rule_result is not None:
        decision, hard_rule_reason = hard_rule_result
        reasoning_trace: dict = {
            "application_id": application.application_id,
            "credit_score": application.credit_score,
            "dti_ratio": round(dti_ratio, 4),
            "hard_rule_triggered": hard_rule_reason,
            "claude_assessment": None,
            "decision": decision,
        }

        await write_audit_log(
            tenant_id=tenant_id,
            actor=_ACTOR,
            action=f"credit_underwriting:{decision}",
            reasoning_trace=reasoning_trace,
            model_version=_MODEL_VERSION,
            execution_id=execution_id,
        )

        return {
            "decision": decision,
            "confidence": 1.0,
            "reasoning": hard_rule_reason,
            "actions_taken": [f"hard_rule_blocked: {hard_rule_reason}"],
            "output_data": {
                "application_id": application.application_id,
                "decision": decision,
                "hard_rule_triggered": hard_rule_reason,
                "credit_score": application.credit_score,
                "dti_ratio": round(dti_ratio, 4),
                "risk_grade": None,
                "risk_factors": [hard_rule_reason],
                "approved_amount_minor": None,
                "interest_rate_bps": None,
                "conditions": [],
                "confidence": 1.0,
                "reasoning": hard_rule_reason,
            },
        }

    # No hard rule triggered — call Claude for full risk assessment
    claude_result = await _call_claude(application, dti_ratio)
    decision = _map_claude_decision(claude_result.risk_assessment)

    reasoning_trace = {
        "application_id": application.application_id,
        "credit_score": application.credit_score,
        "dti_ratio": round(dti_ratio, 4),
        "hard_rule_triggered": None,
        "claude_assessment": {
            "risk_assessment": claude_result.risk_assessment,
            "risk_grade": claude_result.risk_grade,
            "risk_factors": claude_result.risk_factors,
            "approved_amount_minor": claude_result.approved_amount_minor,
            "interest_rate_bps": claude_result.interest_rate_bps,
            "conditions": claude_result.conditions,
            "confidence": claude_result.confidence,
            "reasoning": claude_result.reasoning,
        },
        "decision": decision,
    }

    # Audit log BEFORE updating execution record — operation fails if audit fails
    await write_audit_log(
        tenant_id=tenant_id,
        actor=_ACTOR,
        action=f"credit_underwriting:{decision}",
        reasoning_trace=reasoning_trace,
        model_version=_MODEL_VERSION,
        execution_id=execution_id,
    )

    actions_taken: list[str] = [
        f"credit_assessed: grade={claude_result.risk_grade}, decision={decision}"
    ]

    return {
        "decision": decision,
        "confidence": claude_result.confidence,
        "reasoning": claude_result.reasoning,
        "actions_taken": actions_taken,
        "output_data": {
            "application_id": application.application_id,
            "decision": decision,
            "hard_rule_triggered": None,
            "credit_score": application.credit_score,
            "dti_ratio": round(dti_ratio, 4),
            "risk_grade": claude_result.risk_grade,
            "risk_factors": claude_result.risk_factors,
            "approved_amount_minor": claude_result.approved_amount_minor,
            "interest_rate_bps": claude_result.interest_rate_bps,
            "conditions": claude_result.conditions,
            "confidence": claude_result.confidence,
            "reasoning": claude_result.reasoning,
        },
    }


# ---------------------------------------------------------------------------
# arq job entrypoint
# ---------------------------------------------------------------------------


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
        result = await _execute_credit_underwriting(
            tenant_id, tool_id, execution_id, application_data
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
            settings_obj = get_settings()
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
                function_name="run_credit_underwriting_job",
                error=str(exc),
            )
        raise


# ---------------------------------------------------------------------------
# BaseTool class (orchestrator interface)
# ---------------------------------------------------------------------------


class CreditUnderwritingTool(BaseTool):
    TOOL_TYPE = ToolType.CREDIT_UNDERWRITING
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> ToolOutput:
        execution_id: str = input_data["execution_id"]
        tool_id: str = input_data["tool_id"]
        application_data: dict = input_data["application_data"]

        result = await _execute_credit_underwriting(
            tenant_id, tool_id, execution_id, application_data
        )
        return ToolOutput(
            tool_type=self.TOOL_TYPE,
            decision=result["decision"],
            confidence=result["confidence"],
            reasoning=result["reasoning"],
            actions_taken=result["actions_taken"],
            output_data=result["output_data"],
        )
