"""
Payment Run Tool — sub-agent tool. Called by Financial Orchestrator as a tool.
Identifies approved bills due within the policy window, creates a PaymentRun record,
and routes oversized bills for human approval before any payment is scheduled.
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

_ACTOR = "tool:payment_run:v1"
_MODEL_VERSION = "payment_run-v1"
TOOL_TYPE = ToolType.PAYMENT_RUN


class _ToolPolicy(BaseModel):
    auto_pay_limit_cents: int = 100_000
    approval_threshold_cents: int = 250_000
    due_within_days: int = 7
    max_bills_per_run: int = 50


def _parse_policy(config_json: dict) -> _ToolPolicy:
    raw = config_json.get("policy", config_json)
    return _ToolPolicy(
        auto_pay_limit_cents=raw.get("auto_pay_limit_cents", 100_000),
        approval_threshold_cents=raw.get("approval_threshold_cents", 250_000),
        due_within_days=raw.get("due_within_days", 7),
        max_bills_per_run=raw.get("max_bills_per_run", 50),
    )


class _BillSummary(BaseModel):
    id: str
    contact_name: str | None
    total_cents: int
    outstanding_cents: int
    due_date: str | None
    action: Literal["schedule_payment", "request_approval", "skip"]
    reason: str


class _ClaudeBatchResult(BaseModel):
    batch_valid: bool
    total_auto_pay_cents: int
    total_approval_cents: int
    risk_flags: list[str]
    summary: str


def _classify_bills(bills, policy: _ToolPolicy, today: date) -> list[_BillSummary]:
    cutoff = today + timedelta(days=policy.due_within_days)
    summaries: list[_BillSummary] = []

    for bill in bills[:policy.max_bills_per_run]:
        due = bill.due_date
        if isinstance(due, datetime):
            due = due.date()

        if due is None or due > cutoff:
            summaries.append(_BillSummary(
                id=bill.id,
                contact_name=getattr(bill, "contact_name", None),
                total_cents=bill.total_cents,
                outstanding_cents=bill.outstanding_cents,
                due_date=due.isoformat() if due else None,
                action="skip",
                reason="not_due_within_window",
            ))
            continue

        if bill.outstanding_cents > policy.approval_threshold_cents:
            summaries.append(_BillSummary(
                id=bill.id,
                contact_name=getattr(bill, "contact_name", None),
                total_cents=bill.total_cents,
                outstanding_cents=bill.outstanding_cents,
                due_date=due.isoformat() if due else None,
                action="request_approval",
                reason=f"exceeds_approval_threshold_{policy.approval_threshold_cents}",
            ))
        elif bill.outstanding_cents <= policy.auto_pay_limit_cents:
            summaries.append(_BillSummary(
                id=bill.id,
                contact_name=getattr(bill, "contact_name", None),
                total_cents=bill.total_cents,
                outstanding_cents=bill.outstanding_cents,
                due_date=due.isoformat() if due else None,
                action="schedule_payment",
                reason="within_auto_pay_limit",
            ))
        else:
            summaries.append(_BillSummary(
                id=bill.id,
                contact_name=getattr(bill, "contact_name", None),
                total_cents=bill.total_cents,
                outstanding_cents=bill.outstanding_cents,
                due_date=due.isoformat() if due else None,
                action="request_approval",
                reason="between_auto_and_approval_threshold",
            ))

    return summaries


def _build_prompt(summaries: list[_BillSummary], policy: _ToolPolicy) -> str:
    batch_data = [s.model_dump() for s in summaries if s.action != "skip"]
    total_auto = sum(s.outstanding_cents for s in summaries if s.action == "schedule_payment")
    total_approval = sum(s.outstanding_cents for s in summaries if s.action == "request_approval")

    return (
        "You are a payment operations specialist. Review this payment run batch and return a JSON object "
        "with exactly these fields:\n"
        '  "batch_valid": boolean (true if the batch looks safe to proceed),\n'
        '  "total_auto_pay_cents": integer,\n'
        '  "total_approval_cents": integer,\n'
        '  "risk_flags": array of strings (concerns — empty if none),\n'
        '  "summary": string (1-2 sentences describing the payment run)\n\n'
        "Flag risk if: same vendor appears multiple times in large amounts, "
        "unusual round-number concentrations, or any contact_name looks suspicious.\n"
        "Return ONLY valid JSON. No markdown, no prose.\n\n"
        f"Auto-pay total: {total_auto} cents | Approval-required total: {total_approval} cents\n"
        f"Policy auto_pay_limit: {policy.auto_pay_limit_cents} cents\n\n"
        f"Batch:\n{json.dumps(batch_data, indent=2)}"
    )


async def _call_claude(summaries: list[_BillSummary], policy: _ToolPolicy, settings_obj) -> _ClaudeBatchResult:
    client = AsyncAnthropic(api_key=settings_obj.anthropic_api_key)
    prompt = _build_prompt(summaries, policy)
    last_exc: Exception | None = None

    for attempt in range(settings_obj.max_agent_attempts):
        try:
            message = await client.messages.create(
                model=settings_obj.claude_model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = json.loads(message.content[0].text.strip())
            return _ClaudeBatchResult(**raw)
        except (APIStatusError, APIConnectionError) as exc:
            last_exc = exc
            logger.error("claude_api_error", extra={"attempt": attempt + 1, "error": str(exc)})
            if attempt < settings_obj.max_agent_attempts - 1:
                await asyncio.sleep(settings_obj.backoff_seconds * (attempt + 1))
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            raise RuntimeError(f"Claude returned unparseable response: {exc}") from exc

    raise RuntimeError(f"Claude API failed after {settings_obj.max_agent_attempts} attempts: {last_exc}")


async def _execute(tenant_id: str, tool_id: str, execution_id: str, payload: dict) -> dict:
    settings_obj = get_settings()
    db = get_db()

    tool = await db.tool.find_first(where={"id": tool_id, "tenant_id": tenant_id})
    if tool is None:
        raise ValueError(f"Tool {tool_id} not found for tenant {tenant_id}")

    policy = _parse_policy(tool.config_json if isinstance(tool.config_json, dict) else {})

    bills = await db.accountingbill.find_many(
        where={
            "tenant_id": tenant_id,
            "status": {"not_in": ["paid", "void"]},
            "outstanding_cents": {"gt": 0},
        },
        order={"due_date": "asc"},
    )

    if not bills:
        await write_audit_log(
            tenant_id=tenant_id,
            actor=_ACTOR,
            action="payment_run:no_action",
            reasoning_trace={"reason": "no_outstanding_bills"},
            model_version=_MODEL_VERSION,
            execution_id=execution_id,
        )
        return {
            "decision": "no_action",
            "confidence": 1.0,
            "reasoning": "No outstanding bills found for payment run.",
            "actions_taken": [],
            "output_data": {"bill_count": 0},
        }

    today = date.today()
    summaries = _classify_bills(bills, policy, today)

    scheduled = [s for s in summaries if s.action == "schedule_payment"]
    needs_approval = [s for s in summaries if s.action == "request_approval"]

    if not scheduled and not needs_approval:
        await write_audit_log(
            tenant_id=tenant_id,
            actor=_ACTOR,
            action="payment_run:no_action",
            reasoning_trace={"reason": "no_bills_due_within_window", "policy": policy.model_dump()},
            model_version=_MODEL_VERSION,
            execution_id=execution_id,
        )
        return {
            "decision": "no_action",
            "confidence": 1.0,
            "reasoning": f"No bills due within {policy.due_within_days} days.",
            "actions_taken": [f"scanned {len(bills)} bills — none due within window"],
            "output_data": {"bill_count": len(bills), "due_within_days": policy.due_within_days},
        }

    active_summaries = scheduled + needs_approval
    claude_result = await _call_claude(active_summaries, policy, settings_obj)

    total_auto_cents = sum(s.outstanding_cents for s in scheduled)
    total_approval_cents = sum(s.outstanding_cents for s in needs_approval)
    scheduled_bill_ids = [s.id for s in scheduled]

    if scheduled_bill_ids:
        await db.paymentrun.create(
            data={
                "tenant_id": tenant_id,
                "execution_id": execution_id,
                "status": "scheduled",
                "scheduled_for": datetime.now(UTC) + timedelta(days=1),
                "bill_count": len(scheduled_bill_ids),
                "total_amount_cents": total_auto_cents,
                "bill_ids": scheduled_bill_ids,
            }
        )

    has_risk = bool(claude_result.risk_flags) or not claude_result.batch_valid
    has_approval_bills = bool(needs_approval)

    if has_risk or has_approval_bills:
        overall = "approval_required"
        confidence = 0.85
    else:
        overall = "auto_approved"
        confidence = 0.95

    reasoning_trace = {
        "overall_decision": overall,
        "policy": policy.model_dump(),
        "total_bills_scanned": len(bills),
        "scheduled_count": len(scheduled),
        "approval_required_count": len(needs_approval),
        "total_auto_pay_cents": total_auto_cents,
        "total_approval_cents": total_approval_cents,
        "risk_flags": claude_result.risk_flags,
        "claude_summary": claude_result.summary,
        "per_bill": [s.model_dump() for s in active_summaries],
    }

    await write_audit_log(
        tenant_id=tenant_id,
        actor=_ACTOR,
        action=f"payment_run:{overall}",
        reasoning_trace=reasoning_trace,
        model_version=_MODEL_VERSION,
        execution_id=execution_id,
    )

    actions_taken = [f"scanned {len(bills)} bills, {len(scheduled)} scheduled, {len(needs_approval)} need approval"]
    if scheduled_bill_ids:
        actions_taken.append(f"created payment run for {len(scheduled_bill_ids)} bills totalling {total_auto_cents} cents")
    if claude_result.risk_flags:
        actions_taken.extend(claude_result.risk_flags)

    return {
        "decision": overall,
        "confidence": confidence,
        "reasoning": json.dumps(reasoning_trace),
        "actions_taken": actions_taken,
        "output_data": reasoning_trace,
    }


async def run_payment_run_job(
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
                function_name="run_payment_run_job",
                error=str(exc),
            )
        raise


class PaymentRunTool(BaseTool):
    TOOL_TYPE = ToolType.PAYMENT_RUN
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
