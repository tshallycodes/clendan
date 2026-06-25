"""
Accounts Receivable Tool — sub-agent tool. Called by Financial Orchestrator as a tool.
Analyses overdue AR invoices, classifies urgency, recommends chase actions, and drafts
reminder emails for the most urgent invoices.
"""
from __future__ import annotations

import asyncio
import json
import re
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

_ACTOR = "tool:accounts_receivable:v1"
_MODEL_VERSION = "accounts_receivable-v1"
_LOOKBACK_DAYS = 30
TOOL_TYPE = ToolType.COLLECTIONS


class _ToolPolicy(BaseModel):
    auto_reminder_days: int = 7
    escalate_days: int = 30
    write_off_limit_cents: int = 100_000
    max_chase_attempts: int = 3


_DISCOUNT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)/(\d+)", re.IGNORECASE)


class _InvoiceRecord(BaseModel):
    id: str
    contact_name: str | None
    invoice_number: str | None
    amount_minor: int
    outstanding_cents: int
    due_date: date | None
    issue_date: date | None = None
    days_overdue: int
    status: str
    payment_terms: str | None = None
    early_payment_discount_available: bool = False
    early_payment_discount_pct: float = 0.0
    early_payment_discount_minor: int = 0


class _ClaudeInvoiceResult(BaseModel):
    invoice_id: str
    urgency: Literal["low", "medium", "high"]
    action: Literal["send_reminder", "escalate", "legal_notice", "write_off"]
    reasoning: str


class _ClaudeOutput(BaseModel):
    assessments: list[_ClaudeInvoiceResult]
    top_chase_emails: list[dict]


def _parse_policy(config_json: dict) -> _ToolPolicy:
    raw = config_json.get("policy", config_json)
    return _ToolPolicy(
        auto_reminder_days=raw.get("auto_reminder_days", 7),
        escalate_days=raw.get("escalate_days", 30),
        write_off_limit_cents=raw.get("write_off_limit_cents", 100_000),
        max_chase_attempts=raw.get("max_chase_attempts", 3),
    )


def _detect_early_payment_discounts(invoices: list[_InvoiceRecord]) -> None:
    """Parse payment_terms for early payment discounts (e.g. '2/10 net 30') and annotate invoices in-place."""
    today = date.today()
    for inv in invoices:
        if not inv.payment_terms or not inv.issue_date:
            continue
        match = _DISCOUNT_PATTERN.search(inv.payment_terms)
        if not match:
            continue
        discount_pct = float(match.group(1))
        discount_days = int(match.group(2))
        days_since_issue = (today - inv.issue_date).days
        if days_since_issue <= discount_days:
            inv.early_payment_discount_available = True
            inv.early_payment_discount_pct = discount_pct
            inv.early_payment_discount_minor = round(inv.amount_minor * discount_pct / 100)


def _build_prompt(
    invoices: list[_InvoiceRecord],
    collection_rate_pct: float,
    lookback_days: int,
    total_discount_available_minor: int,
) -> str:
    serialised = json.dumps(
        [
            {
                "invoice_id": inv.id,
                "contact_name": inv.contact_name,
                "invoice_number": inv.invoice_number,
                "amount_minor": inv.amount_minor,
                "outstanding_cents": inv.outstanding_cents,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "days_overdue": inv.days_overdue,
                "status": inv.status,
                "early_payment_discount_available": inv.early_payment_discount_available,
                "early_payment_discount_pct": inv.early_payment_discount_pct,
            }
            for inv in invoices
        ],
        indent=2,
    )
    collection_ctx = (
        f"Collection rate context: {collection_rate_pct:.1f}% of invoices due in the last "
        f"{lookback_days} days have been collected."
    )
    discount_ctx = (
        f"Early payment discount opportunity: offering available discounts across eligible invoices "
        f"could accelerate collection by {total_discount_available_minor} minor currency units."
        if total_discount_available_minor > 0
        else "No early payment discounts are currently available."
    )
    return (
        "You are an accounts receivable specialist. Analyse the overdue invoices below and return "
        "a JSON object with exactly two keys:\n\n"
        '1. "assessments": array where each element has:\n'
        '   "invoice_id": string, "urgency": "low"|"medium"|"high", '
        '"action": "send_reminder"|"escalate"|"legal_notice"|"write_off", "reasoning": string\n'
        "   Rules: 0-15 days overdue → low, 15-30 → medium, 30+ → high\n"
        "   For high-urgency debtors with early_payment_discount_available=true, "
        "recommend in your reasoning whether offering the discount would be effective "
        "based on the invoice value and debtor relationship.\n\n"
        '2. "top_chase_emails": array of up to 3 objects for the most urgent invoices, each with:\n'
        '   "invoice_id": string, "subject": string, "body": string\n\n'
        f"{collection_ctx}\n"
        f"{discount_ctx}\n\n"
        "Return ONLY valid JSON. No markdown, no prose.\n\n"
        f"Invoices:\n{serialised}"
    )


async def _call_claude(
    invoices: list[_InvoiceRecord],
    collection_rate_pct: float,
    lookback_days: int,
    total_discount_available_minor: int,
    settings_obj,
) -> _ClaudeOutput:
    client = AsyncAnthropic(api_key=settings_obj.anthropic_api_key)
    prompt = _build_prompt(invoices, collection_rate_pct, lookback_days, total_discount_available_minor)
    last_exc: Exception | None = None

    for attempt in range(settings_obj.max_agent_attempts):
        try:
            message = await client.messages.create(
                model=settings_obj.claude_model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = json.loads(message.content[0].text.strip())
            return _ClaudeOutput(
                assessments=[_ClaudeInvoiceResult(**a) for a in raw["assessments"]],
                top_chase_emails=raw.get("top_chase_emails", []),
            )
        except (APIStatusError, APIConnectionError) as exc:
            last_exc = exc
            logger.error("claude_api_error", extra={"attempt": attempt + 1, "error": str(exc)})
            if attempt < settings_obj.max_agent_attempts - 1:
                await asyncio.sleep(settings_obj.backoff_seconds * (attempt + 1))
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            raise RuntimeError(f"Claude returned unparseable response: {exc}") from exc

    raise RuntimeError(f"Claude API failed after {settings_obj.max_agent_attempts} attempts: {last_exc}")


def _compute_confidence(collection_rate_pct: float | None) -> float:
    if collection_rate_pct is None:
        return 0.75
    if collection_rate_pct >= 80:
        return 0.95
    if collection_rate_pct >= 50:
        return 0.80
    return 0.65


async def _execute(tenant_id: str, tool_id: str, execution_id: str, payload: dict) -> dict:
    settings_obj = get_settings()
    db = get_db()

    tool = await db.tool.find_first(where={"id": tool_id, "tenant_id": tenant_id})
    if tool is None:
        raise ValueError(f"Tool {tool_id} not found for tenant {tenant_id}")

    policy = _parse_policy(tool.config_json if isinstance(tool.config_json, dict) else {})

    today = date.today()
    lookback_cutoff = datetime.combine(today - timedelta(days=_LOOKBACK_DAYS), datetime.min.time()).replace(tzinfo=UTC)

    # Fetch open/overdue invoices and recently-collected invoices in parallel
    raw_open, raw_collected = await asyncio.gather(
        db.accountinginvoice.find_many(
            where={
                "tenant_id": tenant_id,
                "status": {"in": ["sent", "viewed", "partial", "overdue"]},
                "outstanding_cents": {"gt": 0},
            },
            order={"due_date": "asc"},
        ),
        db.accountinginvoice.find_many(
            where={
                "tenant_id": tenant_id,
                "status": "paid",
                "paid_at": {"gte": lookback_cutoff},
            }
        ),
    )

    if not raw_open:
        await write_audit_log(
            tenant_id=tenant_id,
            actor=_ACTOR,
            action="accounts_receivable:no_action",
            reasoning_trace={"reason": "no_overdue_invoices"},
            model_version=_MODEL_VERSION,
            execution_id=execution_id,
        )
        return {
            "decision": "no_action",
            "confidence": 1.0,
            "reasoning": "No outstanding invoices found.",
            "actions_taken": [],
            "output_data": {"invoice_count": 0},
        }

    def _to_date(val):
        return val.date() if isinstance(val, datetime) else val

    invoices: list[_InvoiceRecord] = []
    for inv in raw_open:
        due = _to_date(inv.due_date)
        issue = _to_date(getattr(inv, "issue_date", None))
        days_overdue = (today - due).days if due and due < today else 0
        invoices.append(
            _InvoiceRecord(
                id=inv.id,
                contact_name=getattr(inv, "contact_name", None),
                invoice_number=getattr(inv, "invoice_number", None),
                amount_minor=inv.outstanding_cents,
                outstanding_cents=inv.outstanding_cents,
                due_date=due,
                issue_date=issue,
                days_overdue=days_overdue,
                status=inv.status,
                payment_terms=getattr(inv, "payment_terms", None),
            )
        )

    _detect_early_payment_discounts(invoices)

    # Run-rate collection projection
    overdue_invoices = [inv for inv in invoices if inv.days_overdue > 0]
    total_overdue_minor = sum(inv.amount_minor for inv in overdue_invoices)
    total_outstanding_minor = sum(inv.amount_minor for inv in invoices)
    recently_collected_minor = sum(getattr(inv, "amount_minor", getattr(inv, "outstanding_cents", 0)) for inv in raw_collected)
    total_due_in_period = recently_collected_minor + total_overdue_minor
    collection_rate_pct: float | None = None
    if total_due_in_period > 0:
        collection_rate_pct = recently_collected_minor / total_due_in_period * 100

    # Early payment discount aggregates
    total_discount_available_minor = sum(inv.early_payment_discount_minor for inv in invoices)
    invoices_with_discount_count = sum(1 for inv in invoices if inv.early_payment_discount_available)

    claude_out = await _call_claude(
        invoices,
        collection_rate_pct if collection_rate_pct is not None else 0.0,
        _LOOKBACK_DAYS,
        total_discount_available_minor,
        settings_obj,
    )

    # Policy check: block write_off if outstanding > limit
    policy_overrides: list[str] = []
    for assessment in claude_out.assessments:
        if assessment.action == "write_off":
            inv_record = next((i for i in invoices if i.id == assessment.invoice_id), None)
            if inv_record and inv_record.outstanding_cents > policy.write_off_limit_cents:
                assessment.action = "escalate"
                policy_overrides.append(
                    f"write_off blocked for invoice {assessment.invoice_id} "
                    f"(outstanding {inv_record.outstanding_cents} > limit {policy.write_off_limit_cents})"
                )

    has_high = any(a.urgency == "high" for a in claude_out.assessments)
    has_medium = any(a.urgency == "medium" for a in claude_out.assessments)
    overall = "escalation_required" if has_high else ("reminders_required" if has_medium else "auto_approved")
    confidence = _compute_confidence(collection_rate_pct)

    reasoning_trace = {
        "overall_decision": overall,
        "invoice_count": len(invoices),
        "collection_rate_pct": round(collection_rate_pct, 2) if collection_rate_pct is not None else None,
        "lookback_days": _LOOKBACK_DAYS,
        "total_overdue_minor": total_overdue_minor,
        "total_outstanding_minor": total_outstanding_minor,
        "recently_collected_minor": recently_collected_minor,
        "total_discount_available_minor": total_discount_available_minor,
        "invoices_with_discount_count": invoices_with_discount_count,
        "policy": policy.model_dump(),
        "policy_overrides": policy_overrides,
        "assessments": [a.model_dump() for a in claude_out.assessments],
        "top_chase_emails": claude_out.top_chase_emails,
    }

    await write_audit_log(
        tenant_id=tenant_id,
        actor=_ACTOR,
        action=f"accounts_receivable:{overall}",
        reasoning_trace=reasoning_trace,
        model_version=_MODEL_VERSION,
        execution_id=execution_id,
    )

    actions_taken = [f"assessed {len(invoices)} overdue invoice(s)"]
    if policy_overrides:
        actions_taken.extend(policy_overrides)
    if invoices_with_discount_count:
        actions_taken.append(
            f"identified {invoices_with_discount_count} invoice(s) with early payment discounts "
            f"totalling {total_discount_available_minor} minor units"
        )
    actions_taken.append(f"drafted {len(claude_out.top_chase_emails)} chase email(s)")

    return {
        "decision": overall,
        "confidence": confidence,
        "reasoning": json.dumps(reasoning_trace),
        "actions_taken": actions_taken,
        "output_data": reasoning_trace,
    }


async def run_accounts_receivable_job(
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
        if result["decision"] == "escalation_required":
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
                function_name="run_accounts_receivable_job",
                error=str(exc),
            )
        raise


class AccountsReceivableTool(BaseTool):
    TOOL_TYPE = ToolType.COLLECTIONS
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
