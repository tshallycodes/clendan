"""
Cash Flow Forecast Tool — sub-agent tool. Called by Financial Orchestrator as a tool.
Builds 30/60/90-day AR/AP buckets, runs scenario analysis, and assesses runway risk.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, date, datetime, timedelta
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

_ACTOR = "tool:cash_flow_forecast:v1"
_MODEL_VERSION = "cash_flow_forecast-v1"
TOOL_TYPE = ToolType.TREASURY


class _ToolPolicy(BaseModel):
    runway_warning_cents: int = 500_000
    forecast_horizon_days: int = 90


def _parse_policy(config_json: dict) -> _ToolPolicy:
    raw = config_json.get("policy", config_json)
    return _ToolPolicy(
        runway_warning_cents=raw.get("runway_warning_cents", 500_000),
        forecast_horizon_days=raw.get("forecast_horizon_days", 90),
    )


class _ForecastBuckets(BaseModel):
    inflows_30: int
    inflows_60: int
    inflows_90: int
    outflows_30: int
    outflows_60: int
    outflows_90: int
    net_30: int
    net_60: int
    net_90: int
    top_ar: list[dict]
    top_ap: list[dict]
    largest_ar_cents: int
    largest_ar_id: str | None


def _build_buckets(ar_rows, ap_rows, today: date) -> _ForecastBuckets:
    day30 = today + timedelta(days=30)
    day60 = today + timedelta(days=60)
    day90 = today + timedelta(days=90)

    def bucket_sum(rows, cutoff: date) -> int:
        return sum(
            r.outstanding_cents
            for r in rows
            if r.due_date and (r.due_date.date() if isinstance(r.due_date, datetime) else r.due_date) <= cutoff
        )

    in30 = bucket_sum(ar_rows, day30)
    in60 = bucket_sum(ar_rows, day60)
    in90 = bucket_sum(ar_rows, day90)
    out30 = bucket_sum(ap_rows, day30)
    out60 = bucket_sum(ap_rows, day60)
    out90 = bucket_sum(ap_rows, day90)

    def top3(rows, label: str) -> list[dict]:
        sorted_rows = sorted(rows, key=lambda r: r.outstanding_cents, reverse=True)[:3]
        return [
            {
                "id": r.id,
                label: r.outstanding_cents,
                "due_date": (r.due_date.date() if isinstance(r.due_date, datetime) else r.due_date).isoformat()
                if r.due_date else None,
            }
            for r in sorted_rows
        ]

    largest_ar = max(ar_rows, key=lambda r: r.outstanding_cents, default=None)

    return _ForecastBuckets(
        inflows_30=in30, inflows_60=in60, inflows_90=in90,
        outflows_30=out30, outflows_60=out60, outflows_90=out90,
        net_30=in30 - out30, net_60=in60 - out60, net_90=in90 - out90,
        top_ar=top3(ar_rows, "outstanding_cents"),
        top_ap=top3(ap_rows, "outstanding_cents"),
        largest_ar_cents=largest_ar.outstanding_cents if largest_ar else 0,
        largest_ar_id=largest_ar.id if largest_ar else None,
    )


def _build_prompt(buckets: _ForecastBuckets, policy: _ToolPolicy) -> str:
    data = {
        "forecast_buckets": {
            "inflows_30_cents": buckets.inflows_30,
            "inflows_60_cents": buckets.inflows_60,
            "inflows_90_cents": buckets.inflows_90,
            "outflows_30_cents": buckets.outflows_30,
            "outflows_60_cents": buckets.outflows_60,
            "outflows_90_cents": buckets.outflows_90,
            "net_30_cents": buckets.net_30,
            "net_60_cents": buckets.net_60,
            "net_90_cents": buckets.net_90,
        },
        "top_3_ar_inflows": buckets.top_ar,
        "top_3_ap_outflows": buckets.top_ap,
        "largest_ar": {
            "id": buckets.largest_ar_id,
            "outstanding_cents": buckets.largest_ar_cents,
        },
        "runway_warning_threshold_cents": policy.runway_warning_cents,
    }
    return (
        "You are a cash flow analyst. Analyse the 30/60/90-day forecast data below and return a JSON object "
        "with exactly these fields:\n"
        '  "risk_level": "low"|"medium"|"high",\n'
        '  "net_30_negative": boolean,\n'
        '  "low_runway_flag": boolean (true if net_30 < runway_warning_threshold),\n'
        '  "scenario_late_ar": string (one sentence: impact if largest AR invoice is 30 days late),\n'
        '  "summary": string (2-3 sentences overall cash flow assessment),\n'
        '  "recommendations": array of up to 3 action strings\n\n'
        "Return ONLY valid JSON. No markdown, no prose.\n\n"
        f"Data:\n{json.dumps(data, indent=2)}"
    )


async def _call_claude(buckets: _ForecastBuckets, policy: _ToolPolicy, settings_obj) -> dict:
    client = AsyncAnthropic(api_key=settings_obj.anthropic_api_key)
    prompt = _build_prompt(buckets, policy)
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

    today = date.today()
    horizon = today + timedelta(days=policy.forecast_horizon_days)

    ar_rows = await db.accountinginvoice.find_many(
        where={
            "tenant_id": tenant_id,
            "outstanding_cents": {"gt": 0},
            "due_date": {"lte": datetime.combine(horizon, datetime.min.time()).replace(tzinfo=UTC)},
        }
    )
    ap_rows = await db.accountingbill.find_many(
        where={
            "tenant_id": tenant_id,
            "outstanding_cents": {"gt": 0},
            "status": {"not_in": ["paid", "void"]},
            "due_date": {"lte": datetime.combine(horizon, datetime.min.time()).replace(tzinfo=UTC)},
        }
    )

    if not ar_rows and not ap_rows:
        await write_audit_log(
            tenant_id=tenant_id,
            actor=_ACTOR,
            action="cash_flow_forecast:no_action",
            reasoning_trace={"reason": "no_forecast_data"},
            model_version=_MODEL_VERSION,
            execution_id=execution_id,
        )
        return {
            "decision": "no_action",
            "confidence": 1.0,
            "reasoning": "No AR or AP data available for forecast.",
            "actions_taken": [],
            "output_data": {"ar_count": 0, "ap_count": 0},
        }

    buckets = _build_buckets(ar_rows, ap_rows, today)
    claude_assessment = await _call_claude(buckets, policy, settings_obj)

    # Policy flag
    low_runway = buckets.net_30 < policy.runway_warning_cents
    risk_level: str = claude_assessment.get("risk_level", "medium")

    if low_runway:
        overall = "low_runway_alert"
    elif risk_level == "high":
        overall = "approval_required"
    else:
        overall = "auto_approved"

    confidence = 0.85 if overall != "auto_approved" else 0.90

    reasoning_trace = {
        "overall_decision": overall,
        "buckets": buckets.model_dump(),
        "policy": policy.model_dump(),
        "low_runway_flag": low_runway,
        "claude_assessment": claude_assessment,
    }

    await write_audit_log(
        tenant_id=tenant_id,
        actor=_ACTOR,
        action=f"cash_flow_forecast:{overall}",
        reasoning_trace=reasoning_trace,
        model_version=_MODEL_VERSION,
        execution_id=execution_id,
    )

    actions_taken = [
        f"forecast built from {len(ar_rows)} AR and {len(ap_rows)} AP records",
        f"net_30={buckets.net_30} net_60={buckets.net_60} net_90={buckets.net_90}",
    ]
    if low_runway:
        actions_taken.append(f"LOW_RUNWAY alert: net_30 {buckets.net_30} < threshold {policy.runway_warning_cents}")

    return {
        "decision": overall,
        "confidence": confidence,
        "reasoning": json.dumps(reasoning_trace),
        "actions_taken": actions_taken,
        "output_data": reasoning_trace,
    }


async def run_cash_flow_forecast_job(
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
        if result["decision"] in ("low_runway_alert", "approval_required"):
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
                function_name="run_cash_flow_forecast_job",
                error=str(exc),
            )
        raise


class CashFlowForecastTool(BaseTool):
    TOOL_TYPE = ToolType.TREASURY
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
