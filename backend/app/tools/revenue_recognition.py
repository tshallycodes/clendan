import asyncio
import json
from calendar import monthrange
from datetime import date, datetime, UTC
from typing import Any

import anthropic
from pydantic import BaseModel

from app.audit.logger import write_audit_log
from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.queue.pool import push_to_dlq
from app.tools.base import BaseTool, ToolOutput, ToolType

_logger = get_logger(__name__)

TOOL_TYPE = "revenue_recognition"
WORKER_VERSION = 1
ACTOR = f"tool:{TOOL_TYPE}:v{WORKER_VERSION}"
MODEL_VERSION = f"{TOOL_TYPE}-v{WORKER_VERSION}"
MIN_CONFIDENCE = 0.4


# ---------------------------------------------------------------------------
# Typed models
# ---------------------------------------------------------------------------

class RecognitionPeriod(BaseModel):
    period: str
    recognised_minor: int
    deferred_minor: int
    reasoning: str


class JournalEntry(BaseModel):
    date: str
    debit_account: str
    credit_account: str
    amount_minor: int
    description: str


class ClaudeRecognitionResult(BaseModel):
    recognition_method: str
    performance_obligations: list[str]
    recognition_schedule: list[RecognitionPeriod]
    journal_entries: list[JournalEntry]
    confidence: float
    reasoning: str


class _ToolPolicy(BaseModel):
    accounting_standard: str = "ASC 606"
    recognition_method: str = "over-time"
    recognition_frequency: str = "daily"                          # "daily" | "monthly"
    variable_consideration_method: str = "expected_value"         # "expected_value" | "most_likely_amount"
    variable_consideration_constraint_enabled: bool = True        # ASC 606 legal requirement
    variable_consideration_review_frequency: str = "each_reporting_date"
    ssp_estimation_method: str = "adjusted_market"                # "adjusted_market" | "expected_cost_plus" | "residual"
    contract_modification_handling: str = "prospective"           # "prospective" | "cumulative_catch_up"
    material_right_tracking_enabled: bool = True
    milestone_completion_threshold_pct: float = 1.00
    auto_close_completed_obligations: bool = True
    period_lock_enforcement: bool = True


def _parse_policy(config_json: dict) -> _ToolPolicy:
    raw = config_json.get("policy", config_json)
    return _ToolPolicy(
        accounting_standard=raw.get("accounting_standard", "ASC 606"),
        recognition_method=raw.get("recognition_method", "over-time"),
        recognition_frequency=raw.get("recognition_frequency", "daily"),
        variable_consideration_method=raw.get("variable_consideration_method", "expected_value"),
        variable_consideration_constraint_enabled=raw.get("variable_consideration_constraint_enabled", True),
        variable_consideration_review_frequency=raw.get("variable_consideration_review_frequency", "each_reporting_date"),
        ssp_estimation_method=raw.get("ssp_estimation_method", "adjusted_market"),
        contract_modification_handling=raw.get("contract_modification_handling", "prospective"),
        material_right_tracking_enabled=raw.get("material_right_tracking_enabled", True),
        milestone_completion_threshold_pct=raw.get("milestone_completion_threshold_pct", 1.00),
        auto_close_completed_obligations=raw.get("auto_close_completed_obligations", True),
        period_lock_enforcement=raw.get("period_lock_enforcement", True),
    )


class ContractInput(BaseModel):
    contract_id: str
    contract_text: str
    total_value_minor: int
    currency: str
    start_date: str
    end_date: str
    accounting_standard: str
    recognition_method: str


# ---------------------------------------------------------------------------
# Schedule calculation (integer arithmetic only)
# ---------------------------------------------------------------------------

def _month_periods(start: date, end: date) -> list[str]:
    """Return YYYY-MM period labels for every month from start through end inclusive."""
    periods: list[str] = []
    year, month = start.year, start.month
    end_ym = (end.year, end.month)
    while (year, month) <= end_ym:
        periods.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    return periods


def _last_day_of_month(period: str) -> str:
    year, month = int(period[:4]), int(period[5:7])
    last = monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-{last:02d}"


def _build_at_point_schedule(
    total_value_minor: int,
    start_date: date,
    currency: str,
    contract_id: str,
) -> tuple[list[RecognitionPeriod], list[JournalEntry]]:
    period = f"{start_date.year:04d}-{start_date.month:02d}"
    schedule = [
        RecognitionPeriod(
            period=period,
            recognised_minor=total_value_minor,
            deferred_minor=0,
            reasoning="At-point recognition: full contract value recognised at service delivery date.",
        )
    ]
    entry_date = _last_day_of_month(period)
    journals = [
        JournalEntry(
            date=entry_date,
            debit_account="Accounts Receivable",
            credit_account="Revenue",
            amount_minor=total_value_minor,
            description=f"Revenue recognised at point of delivery — contract {contract_id}",
        )
    ]
    return schedule, journals


def _build_over_time_schedule(
    total_value_minor: int,
    start: date,
    end: date,
    currency: str,
    contract_id: str,
) -> tuple[list[RecognitionPeriod], list[JournalEntry]]:
    periods = _month_periods(start, end)
    num_months = len(periods)
    if num_months == 0:
        return [], []

    per_month = total_value_minor // num_months
    remainder = total_value_minor - per_month * num_months

    schedule: list[RecognitionPeriod] = []
    journals: list[JournalEntry] = []
    cumulative_recognised = 0

    for idx, period in enumerate(periods):
        amount = per_month + (remainder if idx == num_months - 1 else 0)
        cumulative_recognised += amount
        deferred = total_value_minor - cumulative_recognised
        entry_date = _last_day_of_month(period)

        schedule.append(RecognitionPeriod(
            period=period,
            recognised_minor=amount,
            deferred_minor=deferred,
            reasoning=(
                f"Month {idx + 1} of {num_months}: straight-line over-time recognition. "
                f"{'Includes remainder from integer division.' if idx == num_months - 1 and remainder else ''}"
            ).strip(),
        ))

        journals.append(JournalEntry(
            date=entry_date,
            debit_account="Deferred Revenue",
            credit_account="Revenue",
            amount_minor=amount,
            description=f"Monthly revenue recognition {period} — contract {contract_id}",
        ))

    return schedule, journals


# ---------------------------------------------------------------------------
# Claude call
# ---------------------------------------------------------------------------

_RECOGNITION_PROMPT = """\
You are a revenue recognition specialist applying {standard} accounting rules.
Analyse the contract below and return ONLY a valid JSON object with no markdown.

Contract ID: {contract_id}
Total Value: {total_value_minor} minor units ({currency})
Period: {start_date} to {end_date}
Configured recognition method: {recognition_method}

Contract text:
{contract_text}

Required JSON shape:
{{
  "recognition_method": "at-point|over-time",
  "performance_obligations": ["<string>"],
  "recognition_schedule": [
    {{"period": "YYYY-MM", "recognised_minor": <integer>, "deferred_minor": <integer>, "reasoning": "<string>"}}
  ],
  "journal_entries": [
    {{"date": "YYYY-MM-DD", "debit_account": "<string>", "credit_account": "<string>", "amount_minor": <integer>, "description": "<string>"}}
  ],
  "confidence": <float 0.0-1.0>,
  "reasoning": "<overall reasoning>"
}}

Rules:
- All amounts must be integers (minor units — pence or cents). Never use floats for currency.
- recognition_method must match the configured method unless the contract clearly contradicts it.
- Include one schedule entry per month for over-time, one entry for at-point.
- Return ONLY the JSON object.
"""


async def _call_claude(validated: ContractInput) -> ClaudeRecognitionResult:
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    prompt = _RECOGNITION_PROMPT.format(
        standard=validated.accounting_standard,
        contract_id=validated.contract_id,
        total_value_minor=validated.total_value_minor,
        currency=validated.currency,
        start_date=validated.start_date,
        end_date=validated.end_date,
        recognition_method=validated.recognition_method,
        contract_text=validated.contract_text,
    )

    last_exc: Exception = RuntimeError("No attempts made")
    for attempt in range(settings.max_agent_attempts):
        try:
            response = await client.messages.create(
                model=settings.claude_model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = response.content[0].text.strip()
            data = json.loads(raw_text)
            return ClaudeRecognitionResult(**data)
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            last_exc = exc
            _logger.warning(
                "claude_transient_error",
                extra={"attempt": attempt + 1, "error": str(exc)},
            )
            if attempt < settings.max_agent_attempts - 1:
                await asyncio.sleep(settings.backoff_seconds * (attempt + 1))
        except (json.JSONDecodeError, Exception) as exc:
            raise ValueError(f"Claude returned unparseable response: {exc}") from exc

    raise RuntimeError(
        f"Claude API failed after {settings.max_agent_attempts} attempts: {last_exc}"
    ) from last_exc


# ---------------------------------------------------------------------------
# Core execution
# ---------------------------------------------------------------------------

async def _execute_revenue_recognition(
    tenant_id: str,
    tool_id: str,
    execution_id: str,
    contract_data: dict[str, Any],
) -> dict[str, Any]:
    validated = ContractInput(**contract_data)

    start = date.fromisoformat(validated.start_date)
    end = date.fromisoformat(validated.end_date)

    if end < start:
        raise ValueError(f"end_date {validated.end_date} is before start_date {validated.start_date}")

    claude_result = await _call_claude(validated)

    if claude_result.confidence < MIN_CONFIDENCE:
        raise ValueError(
            f"Claude recognition confidence {claude_result.confidence} is below minimum {MIN_CONFIDENCE}"
        )

    effective_method = validated.recognition_method
    if claude_result.recognition_method in ("at-point", "over-time"):
        effective_method = claude_result.recognition_method

    if effective_method == "at-point":
        schedule, journals = _build_at_point_schedule(
            validated.total_value_minor, start, validated.currency, validated.contract_id
        )
    else:
        schedule, journals = _build_over_time_schedule(
            validated.total_value_minor, start, end, validated.currency, validated.contract_id
        )

    num_periods = len(schedule)

    minor_symbol_map = {"GBP": "£", "USD": "$", "EUR": "€"}
    symbol = minor_symbol_map.get(validated.currency, validated.currency)

    actions_taken: list[str] = [
        f"Scheduled {entry.period}: {symbol}{entry.recognised_minor / 100:.2f}"
        for entry in schedule
    ]

    reasoning_trace: dict[str, Any] = {
        "contract_id": validated.contract_id,
        "accounting_standard": validated.accounting_standard,
        "recognition_method": effective_method,
        "total_value_minor": validated.total_value_minor,
        "currency": validated.currency,
        "start_date": validated.start_date,
        "end_date": validated.end_date,
        "num_periods": num_periods,
        "performance_obligations": claude_result.performance_obligations,
        "schedule_summary": [
            {"period": s.period, "recognised_minor": s.recognised_minor}
            for s in schedule
        ],
        "claude_reasoning": claude_result.reasoning,
        "claude_confidence": claude_result.confidence,
    }

    await write_audit_log(
        tenant_id=tenant_id,
        actor=ACTOR,
        action="revenue_recognition_scheduled",
        reasoning_trace=reasoning_trace,
        model_version=MODEL_VERSION,
        execution_id=execution_id,
    )

    return {
        "decision": "revenue_scheduled",
        "confidence": claude_result.confidence,
        "reasoning": claude_result.reasoning,
        "actions_taken": actions_taken,
        "recognition_method": effective_method,
        "accounting_standard": validated.accounting_standard,
        "performance_obligations": claude_result.performance_obligations,
        "recognition_schedule": [s.model_dump() for s in schedule],
        "journal_entries": [j.model_dump() for j in journals],
        "contract_id": validated.contract_id,
        "total_value_minor": validated.total_value_minor,
        "currency": validated.currency,
        "num_periods": num_periods,
    }


# ---------------------------------------------------------------------------
# arq job entry point
# ---------------------------------------------------------------------------

async def run_revenue_recognition_job(
    ctx: dict,
    *,
    execution_id: str,
    tenant_id: str,
    tool_id: str,
    contract_data: dict,
) -> dict:
    import time

    db = get_db()
    start_ms = int(time.time() * 1000)

    try:
        result = await _execute_revenue_recognition(
            tenant_id, tool_id, execution_id, contract_data
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
                function_name="run_revenue_recognition_job",
                error=str(exc),
            )
        raise


# ---------------------------------------------------------------------------
# BaseTool adapter (Orchestrator interface)
# ---------------------------------------------------------------------------

class RevenueRecognitionTool(BaseTool):
    TOOL_TYPE = ToolType.REVENUE_RECOGNITION
    REQUIRED_TOOLS: list[str] = []
    VERSION = WORKER_VERSION

    async def execute(self, input_data: dict[str, Any], tenant_id: str) -> ToolOutput:
        validated = ContractInput(**input_data)

        start = date.fromisoformat(validated.start_date)
        end = date.fromisoformat(validated.end_date)

        if end < start:
            raise ValueError(
                f"end_date {validated.end_date} is before start_date {validated.start_date}"
            )

        claude_result = await _call_claude(validated)

        if claude_result.confidence < MIN_CONFIDENCE:
            raise ValueError(
                f"Claude recognition confidence {claude_result.confidence} is below minimum {MIN_CONFIDENCE}"
            )

        effective_method = validated.recognition_method
        if claude_result.recognition_method in ("at-point", "over-time"):
            effective_method = claude_result.recognition_method

        if effective_method == "at-point":
            schedule, journals = _build_at_point_schedule(
                validated.total_value_minor, start, validated.currency, validated.contract_id
            )
        else:
            schedule, journals = _build_over_time_schedule(
                validated.total_value_minor, start, end, validated.currency, validated.contract_id
            )

        minor_symbol_map = {"GBP": "£", "USD": "$", "EUR": "€"}
        symbol = minor_symbol_map.get(validated.currency, validated.currency)

        actions_taken: list[str] = [
            f"Scheduled {entry.period}: {symbol}{entry.recognised_minor / 100:.2f}"
            for entry in schedule
        ]

        return ToolOutput(
            tool_type=self.TOOL_TYPE,
            decision="revenue_scheduled",
            confidence=claude_result.confidence,
            reasoning=claude_result.reasoning,
            actions_taken=actions_taken,
            output_data={
                "recognition_method": effective_method,
                "accounting_standard": validated.accounting_standard,
                "performance_obligations": claude_result.performance_obligations,
                "recognition_schedule": [s.model_dump() for s in schedule],
                "journal_entries": [j.model_dump() for j in journals],
                "contract_id": validated.contract_id,
                "total_value_minor": validated.total_value_minor,
                "currency": validated.currency,
                "num_periods": len(schedule),
            },
        )
