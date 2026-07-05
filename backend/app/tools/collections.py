from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

import anthropic
from pydantic import BaseModel

from app.audit.logger import write_audit_log
from app.core.config import get_settings
from app.core.db import get_db
from app.core.execution import complete_execution
from app.core.logging import get_logger
from app.queue.pool import push_to_dlq
from app.tools.base import BaseTool, ToolOutput, ToolType

_logger = get_logger(__name__)

TOOL_TYPE = "collections"
TOOL_VERSION = 1
ACTOR = "tool:collections:v1"
MODEL_VERSION = "collections-v1"
CONFIDENCE = 0.95

Tone = Literal["reminder", "escalation", "legal"]
RecommendedAction = Literal["send_reminder", "escalate", "initiate_legal"]


class _InvoiceRow(BaseModel):
    id: str
    vendor: str
    invoice_number: str
    amount_minor: int
    currency: str
    due_date: date
    days_overdue: int
    tone: Tone
    recommended_action: RecommendedAction


class _ClaudeMessage(BaseModel):
    message: str
    tone: Tone
    recommended_action: RecommendedAction
    reasoning: str


class _ToolConfig(BaseModel):
    first_reminder_days: int = 7
    escalate_days: int = 30
    legal_days: int = 60
    reminder_1_days_overdue: int = 3
    reminder_2_days_overdue: int = 14
    reminder_3_days_overdue: int = 30
    final_notice_days_overdue: int = 60
    do_not_contact_start: int = 21               # 9pm — LEGAL REQUIREMENT (CFPB Reg F)
    do_not_contact_end: int = 8                  # 8am — LEGAL REQUIREMENT (CFPB Reg F)
    max_calls_per_debt_per_week: int = 7         # LEGAL MAXIMUM (CFPB Reg F)
    late_fee_enabled: bool = True
    late_fee_fixed_amount: int = 4000            # minor units ($40)
    late_fee_rate_annual_bps: int = 1800         # 18% annualised
    late_fee_max_per_invoice_pct: float = 0.15
    payment_plan_enabled: bool = True
    payment_plan_min_installments: int = 2
    payment_plan_max_months: int = 12
    dispute_hold_enabled: bool = True
    dispute_resolution_days: int = 30
    minimum_balance_for_collections: int = 5000  # minor units ($50)


def _amount_display(amount_minor: int, currency: str) -> str:
    symbol = {"GBP": "£", "USD": "$", "EUR": "€"}.get(currency, currency + " ")
    return f"{symbol}{amount_minor / 100:.2f}"


def _classify_tone(days_overdue: int, cfg: _ToolConfig) -> tuple[Tone, RecommendedAction] | None:
    if days_overdue < cfg.first_reminder_days:
        return None
    if days_overdue < cfg.escalate_days:
        return "reminder", "send_reminder"
    if days_overdue < cfg.legal_days:
        return "escalation", "escalate"
    return "legal", "initiate_legal"


def _build_batch_prompt(invoices: list[_InvoiceRow], tone: Tone) -> str:
    tone_instructions = {
        "reminder": (
            "Write a polite, professional payment reminder. Acknowledge the invoice may have "
            "slipped through and invite the customer to arrange payment promptly."
        ),
        "escalation": (
            "Write a firm but professional overdue notice. Make clear that the account is "
            "significantly overdue, request immediate payment, and state that further action "
            "may follow if payment is not received within 7 days."
        ),
        "legal": (
            "Write a formal legal warning letter. State that the account has been referred for "
            "legal recovery proceedings and that legal action will commence unless full payment "
            "is received within 14 days."
        ),
    }

    invoice_list = "\n".join(
        f"- Invoice {inv.invoice_number} | Vendor: {inv.vendor} | "
        f"Amount: {_amount_display(inv.amount_minor, inv.currency)} | "
        f"Days overdue: {inv.days_overdue}"
        for inv in invoices
    )

    return f"""You are a financial collections assistant for a business.

Tone instruction: {tone_instructions[tone]}

For EACH invoice below, return a JSON array where each element has:
- "invoice_number": the invoice number as provided
- "message": the collection message to send
- "tone": "{tone}"
- "recommended_action": "{'send_reminder' if tone == 'reminder' else 'escalate' if tone == 'escalation' else 'initiate_legal'}"
- "reasoning": brief explanation of why this tone is appropriate

Invoices:
{invoice_list}

Return ONLY a valid JSON array. No markdown, no explanation."""


async def _call_claude_batch(
    invoices: list[_InvoiceRow],
    tone: Tone,
    client: anthropic.AsyncAnthropic,
    settings: Any,
) -> dict[str, _ClaudeMessage]:
    """Call Claude for a batch of invoices sharing the same tone. Returns mapping of invoice_number → message."""
    prompt = _build_batch_prompt(invoices, tone)
    last_exc: Exception = RuntimeError("No attempts made")

    for attempt in range(settings.max_agent_attempts):
        try:
            response = await client.messages.create(
                model=settings.claude_model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            parsed: list[dict] = json.loads(raw)
            result: dict[str, _ClaudeMessage] = {}
            for item in parsed:
                msg = _ClaudeMessage(
                    message=item["message"],
                    tone=item["tone"],
                    recommended_action=item["recommended_action"],
                    reasoning=item["reasoning"],
                )
                result[item["invoice_number"]] = msg
            return result
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            last_exc = exc
            if attempt < settings.max_agent_attempts - 1:
                await asyncio.sleep(settings.backoff_seconds * (attempt + 1))
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            raise ValueError(f"Claude returned unparseable response for tone={tone}: {exc}") from exc

    raise RuntimeError(
        f"Claude API failed after {settings.max_agent_attempts} attempts for tone={tone}: {last_exc}"
    ) from last_exc


async def _execute_collections(
    tenant_id: str,
    tool_id: str,
    execution_id: str,
) -> dict[str, Any]:
    db = get_db()
    settings = get_settings()
    today = date.today()

    tool_record = await db.tool.find_first(
        where={"id": tool_id, "tenant_id": tenant_id}
    )
    if tool_record is None:
        raise ValueError(f"Tool {tool_id} not found for tenant {tenant_id}")

    raw_config: dict = tool_record.config_json or {}
    cfg = _ToolConfig(
        first_reminder_days=raw_config.get("first_reminder_days", 7),
        escalate_days=raw_config.get("escalate_days", 30),
        legal_days=raw_config.get("legal_days", 60),
        reminder_1_days_overdue=raw_config.get("reminder_1_days_overdue", 3),
        reminder_2_days_overdue=raw_config.get("reminder_2_days_overdue", 14),
        reminder_3_days_overdue=raw_config.get("reminder_3_days_overdue", 30),
        final_notice_days_overdue=raw_config.get("final_notice_days_overdue", 60),
        do_not_contact_start=raw_config.get("do_not_contact_start", 21),
        do_not_contact_end=raw_config.get("do_not_contact_end", 8),
        max_calls_per_debt_per_week=raw_config.get("max_calls_per_debt_per_week", 7),
        late_fee_enabled=raw_config.get("late_fee_enabled", True),
        late_fee_fixed_amount=raw_config.get("late_fee_fixed_amount", 4000),
        late_fee_rate_annual_bps=raw_config.get("late_fee_rate_annual_bps", 1800),
        late_fee_max_per_invoice_pct=raw_config.get("late_fee_max_per_invoice_pct", 0.15),
        payment_plan_enabled=raw_config.get("payment_plan_enabled", True),
        payment_plan_min_installments=raw_config.get("payment_plan_min_installments", 2),
        payment_plan_max_months=raw_config.get("payment_plan_max_months", 12),
        dispute_hold_enabled=raw_config.get("dispute_hold_enabled", True),
        dispute_resolution_days=raw_config.get("dispute_resolution_days", 30),
        minimum_balance_for_collections=raw_config.get("minimum_balance_for_collections", 5000),
    )

    raw_invoices = await db.invoice.find_many(
        where={
            "tenant_id": tenant_id,
            "due_date": {"lt": today},
            "status": {"not_in": ["paid", "cancelled"]},
        }
    )

    if not raw_invoices:
        reasoning_trace: dict[str, Any] = {
            "total_overdue_count": 0,
            "actions_by_tone": {"reminder": [], "escalation": [], "legal": []},
            "invoice_ids_processed": [],
            "tool_config": cfg.model_dump(),
        }
        await write_audit_log(
            tenant_id=tenant_id,
            actor=ACTOR,
            action="collections_run",
            reasoning_trace=reasoning_trace,
            model_version=MODEL_VERSION,
            execution_id=execution_id,
        )
        return {
            "decision": "auto_approved",
            "confidence": CONFIDENCE,
            "reasoning": "No overdue invoices",
            "actions_taken": [],
            "total_overdue": 0,
        }

    buckets: dict[Tone, list[_InvoiceRow]] = {
        "reminder": [],
        "escalation": [],
        "legal": [],
    }

    for inv in raw_invoices:
        days_overdue = (today - inv.due_date).days
        classified = _classify_tone(days_overdue, cfg)
        if classified is None:
            continue
        tone, action = classified
        buckets[tone].append(
            _InvoiceRow(
                id=inv.id,
                vendor=inv.vendor,
                invoice_number=inv.invoice_number,
                amount_minor=inv.amount_minor,
                currency=inv.currency,
                due_date=inv.due_date,
                days_overdue=days_overdue,
                tone=tone,
                recommended_action=action,
            )
        )

    all_actionable = buckets["reminder"] + buckets["escalation"] + buckets["legal"]

    if not all_actionable:
        reasoning_trace = {
            "total_overdue_count": len(raw_invoices),
            "actions_by_tone": {"reminder": [], "escalation": [], "legal": []},
            "invoice_ids_processed": [],
            "note": "All overdue invoices are within the first_reminder_days threshold",
            "tool_config": cfg.model_dump(),
        }
        await write_audit_log(
            tenant_id=tenant_id,
            actor=ACTOR,
            action="collections_run",
            reasoning_trace=reasoning_trace,
            model_version=MODEL_VERSION,
            execution_id=execution_id,
        )
        return {
            "decision": "auto_approved",
            "confidence": CONFIDENCE,
            "reasoning": "No invoices have reached the first reminder threshold",
            "actions_taken": [],
            "total_overdue": len(raw_invoices),
        }

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    claude_results: dict[str, _ClaudeMessage] = {}

    for tone, invoice_list in buckets.items():
        if not invoice_list:
            continue
        batch_result = await _call_claude_batch(invoice_list, tone, client, settings)
        claude_results.update(batch_result)

    actions_taken: list[str] = []
    actions_by_tone: dict[str, list[str]] = {"reminder": [], "escalation": [], "legal": []}
    processed_ids: list[str] = []

    for inv in all_actionable:
        msg_data = claude_results.get(inv.invoice_number)
        action_label = (
            msg_data.recommended_action if msg_data else inv.recommended_action
        )
        summary = (
            f"{inv.invoice_number}: {action_label.replace('_', ' ')} "
            f"({inv.days_overdue} days overdue)"
        )
        actions_taken.append(summary)
        actions_by_tone[inv.tone].append(inv.invoice_number)
        processed_ids.append(inv.id)

    if processed_ids:
        await db.invoice.update_many(
            where={"id": {"in": processed_ids}, "tenant_id": tenant_id},
            data={"status": "overdue"},
        )

    has_legal = bool(buckets["legal"])
    has_escalation = bool(buckets["escalation"])

    if has_legal:
        overall_decision = "blocked"
    elif has_escalation:
        overall_decision = "approval_required"
    else:
        overall_decision = "auto_approved"

    reasoning_trace = {
        "total_overdue_count": len(raw_invoices),
        "total_actionable_count": len(all_actionable),
        "actions_by_tone": {
            "reminder": actions_by_tone["reminder"],
            "escalation": actions_by_tone["escalation"],
            "legal": actions_by_tone["legal"],
        },
        "invoice_ids_processed": processed_ids,
        "overall_decision": overall_decision,
        "tool_config": cfg.model_dump(),
    }

    await write_audit_log(
        tenant_id=tenant_id,
        actor=ACTOR,
        action="collections_run",
        reasoning_trace=reasoning_trace,
        model_version=MODEL_VERSION,
        execution_id=execution_id,
    )

    reasoning_summary = (
        f"Processed {len(all_actionable)} overdue invoice(s): "
        f"{len(buckets['reminder'])} reminder(s), "
        f"{len(buckets['escalation'])} escalation(s), "
        f"{len(buckets['legal'])} legal notice(s)."
    )

    return {
        "decision": overall_decision,
        "confidence": CONFIDENCE,
        "reasoning": reasoning_summary,
        "actions_taken": actions_taken,
        "total_overdue": len(raw_invoices),
        "actions_by_tone": actions_by_tone,
    }


async def run_collections_job(
    ctx: dict,
    *,
    execution_id: str,
    tenant_id: str,
    tool_id: str,
) -> dict:
    db = get_db()
    start_ms = int(time.time() * 1000)
    try:
        result = await _execute_collections(tenant_id, tool_id, execution_id)
        duration_ms = int(time.time() * 1000) - start_ms

        await complete_execution(
            db=db, execution_id=execution_id, tool_id=tool_id,
            tenant_id=tenant_id, decision=result["decision"],
            confidence=result["confidence"], duration_ms=duration_ms,
        )

        _logger.info(
            "collections_job_completed",
            extra={
                "tenant_id": tenant_id,
                "execution_id": execution_id,
                "decision": result["decision"],
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
                function_name="run_collections_job",
                error=str(exc),
            )

        _logger.error(
            "collections_job_failed",
            extra={
                "tenant_id": tenant_id,
                "execution_id": execution_id,
                "error": str(exc),
            },
        )
        raise


class CollectionsTool(BaseTool):
    """Orchestrator-facing adapter. Delegates to _execute_collections."""
    TOOL_TYPE = ToolType.COLLECTIONS
    REQUIRED_TOOLS = ["invoice_system_api", "email_dispatch_api"]
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> ToolOutput:
        tool_id = input_data.get("tool_id", "")
        execution_id = input_data.get("execution_id", "")
        result = await _execute_collections(tenant_id, tool_id, execution_id)
        return ToolOutput(
            tool_type=self.TOOL_TYPE,
            decision=result["decision"],
            confidence=result["confidence"],
            reasoning=result["reasoning"],
            actions_taken=result.get("actions_taken", []),
            output_data=result,
        )
