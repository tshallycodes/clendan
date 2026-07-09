"""
Accounts Receivable & Collections Tool - the AR workflow.

Ages outstanding customer invoices and recommends tiered collection actions
(reminder -> second reminder -> final notice -> escalate -> write-off candidate) per the
tenant's collections policy. Gentle reminders auto-approve when enabled; firmer actions
(final notice, escalation, late fees, write-offs) route to a human for approval.

MVP scope: it decides and records the recommended action per invoice. Actually sending
reminder emails and posting late fees / write-offs to the ERP is a deferred execution layer
(mirrors Payment Runs, which schedules but does not yet move money) - it must land behind
its own design review because it is an outbound, customer-facing action.
"""
from __future__ import annotations

import json
import time
from datetime import UTC, datetime

from pydantic import BaseModel

from app.audit.logger import write_audit_log
from app.core.db import get_db
from app.core.execution import complete_execution
from app.core.logging import get_logger
from app.core.sources import source_filter
from app.queue.pool import push_to_dlq
from app.tools.base import BaseTool, ToolOutput, ToolType

logger = get_logger(__name__)

_ACTOR = "tool:ar_collections:v1"
_MODEL_VERSION = "ar_collections-v1"
TOOL_TYPE = ToolType.AR_COLLECTIONS
_TOOL_VERSION = 1

# Invoice statuses that are not collectible-actionable.
_SETTLED_STATUSES = {"paid", "voided", "deleted", "draft"}

# Actions that must never happen without a human sign-off.
_APPROVAL_ACTIONS = {"final_notice", "escalate", "write_off_candidate"}


class _ToolPolicy(BaseModel):
    reminder_1_days: int = 0        # days overdue to send a gentle reminder (0 = on due date)
    reminder_2_days: int = 7        # days overdue for a second reminder
    final_notice_days: int = 14     # days overdue for a final notice
    escalate_days: int = 30         # days overdue to escalate
    write_off_days: int = 120       # days overdue to flag as a write-off candidate
    auto_send_reminders: bool = True  # reminders auto-approve; firmer actions still need approval
    late_fee_percent: float = 0.0   # 0 = no late fees
    late_fee_after_days: int = 30
    write_off_max_cents: int = 5000  # only auto-suggest write-off below this amount


def _parse_policy(config_json: dict | None) -> _ToolPolicy:
    raw = config_json or {}
    raw = raw.get("policy", raw)
    return _ToolPolicy(**{k: v for k, v in raw.items() if k in _ToolPolicy.model_fields})


def _days_overdue(due_date, now: datetime) -> int | None:
    """Signed days past due: negative = not yet due, None = no due date (cannot age)."""
    if not due_date:
        return None
    due = due_date if due_date.tzinfo else due_date.replace(tzinfo=UTC)
    return (now - due).days


def _tier_for(days: int, policy: _ToolPolicy) -> tuple[str, str]:
    """Return (action, human tier label) for an invoice this many days overdue."""
    if days >= policy.write_off_days:
        return "write_off_candidate", "write-off candidate"
    if days >= policy.escalate_days:
        return "escalate", "escalate"
    if days >= policy.final_notice_days:
        return "final_notice", "final notice"
    if days >= policy.reminder_2_days:
        return "second_reminder", "second reminder"
    if days >= policy.reminder_1_days:
        return "reminder", "reminder"
    return "none", "not yet due for action"


async def _execute(tenant_id: str, tool_id: str, execution_id: str, payload: dict) -> dict:
    db = get_db()
    tool = await db.tool.find_first(where={"id": tool_id, "tenant_id": tenant_id})
    config = tool.config_json if tool and isinstance(tool.config_json, dict) else {}
    policy = _parse_policy(config)
    now = datetime.now(UTC)

    # AR = customer/sales invoices (supplier bills live in AccountingBill). Scope to the
    # configured accounting sources and only genuinely outstanding balances.
    src = source_filter(config, "accounting_sources")
    invoices = await db.accountinginvoice.find_many(
        where={"tenant_id": tenant_id, **src, "outstanding_cents": {"gt": 0}},
    )
    outstanding = [inv for inv in invoices if (inv.status or "").lower() not in _SETTLED_STATUSES]

    if not outstanding:
        await write_audit_log(
            tenant_id=tenant_id, actor=_ACTOR, action="ar_collections:no_action",
            reasoning_trace={"reason": "no_outstanding_invoices"},
            model_version=_MODEL_VERSION, execution_id=execution_id,
        )
        return {
            "decision": "auto_approved", "confidence": 1.0,
            "reasoning": "No outstanding customer invoices to collect.",
            "actions_taken": [], "output_data": {"outstanding_count": 0},
        }

    items: list[dict] = []
    total_outstanding = 0
    overdue_count = 0
    overdue_amount = 0
    tier_counts: dict[str, int] = {}
    late_fee_cents_total = 0
    needs_approval = False

    for inv in outstanding:
        out_cents = int(inv.outstanding_cents or 0)
        total_outstanding += out_cents
        days = _days_overdue(inv.due_date, now)
        if days is None:
            continue  # no due date - cannot determine collection timing
        if days > 0:
            overdue_count += 1
            overdue_amount += out_cents

        action, tier_label = _tier_for(days, policy)
        if action == "none":
            continue
        tier_counts[action] = tier_counts.get(action, 0) + 1

        late_fee = 0
        if policy.late_fee_percent > 0 and days >= policy.late_fee_after_days:
            late_fee = round(out_cents * policy.late_fee_percent / 100)
            late_fee_cents_total += late_fee

        # Reminders auto-send when enabled; a large write-off is never auto even under the
        # write-off tier. Everything in _APPROVAL_ACTIONS and any late fee needs a human.
        if action in ("reminder", "second_reminder"):
            requires_approval = not policy.auto_send_reminders
        else:
            requires_approval = True
        if late_fee > 0:
            requires_approval = True
        if action == "write_off_candidate" and out_cents > policy.write_off_max_cents:
            requires_approval = True
        if requires_approval:
            needs_approval = True

        items.append({
            "invoice_id": inv.id,
            "number": getattr(inv, "number", None),
            "contact_name": getattr(inv, "contact_name", None),
            "outstanding_cents": out_cents,
            "currency": inv.currency,
            "days_overdue": days,
            "action": action,
            "tier": tier_label,
            "late_fee_cents": late_fee,
            "requires_approval": requires_approval,
        })

    decision = "approval_required" if needs_approval else "auto_approved"

    reasoning_trace = {
        "decision": decision,
        "outstanding_count": len(outstanding),
        "total_outstanding_cents": total_outstanding,
        "overdue_count": overdue_count,
        "overdue_amount_cents": overdue_amount,
        "tier_counts": tier_counts,
        "late_fee_cents_total": late_fee_cents_total,
        "action_count": len(items),
        "items": items,
        "policy": policy.model_dump(),
        "note": (
            "MVP records recommended collection actions; sending reminders and posting late "
            "fees / write-offs is a deferred outbound execution layer."
        ),
    }

    await write_audit_log(
        tenant_id=tenant_id, actor=_ACTOR, action=f"ar_collections:{decision}",
        reasoning_trace=reasoning_trace, model_version=_MODEL_VERSION, execution_id=execution_id,
    )

    actions_taken = [
        f"aged {len(outstanding)} outstanding invoice(s); {overdue_count} overdue",
        f"recommended {len(items)} collection action(s)",
    ]
    for action, n in sorted(tier_counts.items()):
        actions_taken.append(f"{action}: {n}")
    if late_fee_cents_total:
        actions_taken.append(f"late fees recommended: {late_fee_cents_total} cents")

    return {
        "decision": decision, "confidence": 0.9,
        "reasoning": json.dumps(reasoning_trace),
        "actions_taken": actions_taken, "output_data": reasoning_trace,
    }


async def run_ar_collections_job(
    ctx: dict,
    *,
    execution_id: str,
    tenant_id: str,
    tool_id: str,
    payload: dict,
    policy_config: dict,
) -> dict:
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
            await push_to_dlq(
                job_id=str(ctx.get("job_id", "unknown")),
                function_name="run_ar_collections_job", error=str(exc),
            )
        raise


class ARCollectionsTool(BaseTool):
    TOOL_TYPE = ToolType.AR_COLLECTIONS
    VERSION = _TOOL_VERSION

    async def execute(self, input_data: dict, tenant_id: str) -> ToolOutput:
        result = await _execute(
            tenant_id, input_data["tool_id"], input_data["execution_id"], input_data.get("payload", {}),
        )
        return ToolOutput(
            tool_type=self.TOOL_TYPE, decision=result["decision"], confidence=result["confidence"],
            reasoning=result["reasoning"], actions_taken=result["actions_taken"],
            output_data=result["output_data"],
        )
