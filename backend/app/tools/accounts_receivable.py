"""
Accounts Receivable & Collections Tool - the AR workflow.

Ages outstanding customer invoices and recommends tiered collection actions
(reminder -> second reminder -> final notice -> escalate -> write-off candidate) per the
tenant's collections policy. Gentle reminders auto-approve when enabled; firmer actions
(final notice, escalation, late fees, write-offs) route to a human for approval.

Auto-approved reminder tiers (reminder / second reminder) are now dispatched from the
tenant's connected mailbox via app/core/mailer.py - dry-run by default (recorded as
"would send") until emails_live is enabled. Each tier is sent at most once per invoice
(deduped through the CollectionReminder log). Firmer, customer-facing actions (final notice,
escalation, late fees, write-offs) still route to a human for approval and are not auto-sent.
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
from app.core.mailer import MailError, send_via_mailbox
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


# Tiers that auto-send as a plain reminder (never firmer notices, which need approval).
_AUTO_SEND_TIERS = {"reminder", "second_reminder"}
_CCY_SYMBOLS = {"GBP": "£", "USD": "$", "EUR": "€"}


def _fmt_amount(cents: int, currency: str) -> str:
    sym = _CCY_SYMBOLS.get((currency or "GBP").upper(), "")
    base = f"{cents / 100:,.2f}"
    return f"{sym}{base}" if sym else f"{base} {(currency or 'GBP').upper()}"


def _reminder_message(item: dict) -> tuple[str, str]:
    """Build (subject, plain-text body) for an auto-send reminder tier."""
    number = item.get("number") or "your invoice"
    name = item.get("contact_name") or "there"
    amount = _fmt_amount(item["outstanding_cents"], item.get("currency") or "GBP")
    days = item.get("days_overdue") or 0
    if item["action"] == "second_reminder":
        subject = f"Second reminder: invoice {number} ({amount} outstanding)"
        opener = f"We haven't yet received payment for invoice {number}, now {days} days overdue."
    else:
        subject = f"Reminder: invoice {number} ({amount} outstanding)"
        opener = (
            f"This is a friendly reminder that invoice {number} for {amount} is now due."
            if days <= 0
            else f"This is a friendly reminder that invoice {number} for {amount} is {days} days overdue."
        )
    body = (
        f"Hi {name},\n\n{opener}\n\n"
        f"Amount outstanding: {amount}\n\n"
        "If you've already sent payment, please disregard this note. Otherwise we'd be grateful "
        "if you could arrange payment at your earliest convenience.\n\n"
        "If you have any questions about this invoice, just reply to this email.\n\n"
        "Many thanks."
    )
    return subject, body


async def _dispatch_auto_reminders(db, tenant_id: str, items: list[dict]) -> dict:
    """Send the auto-approved reminder tiers via the tenant's mailbox (dry-run unless
    emails_live). Deduped per (invoice, tier) on prior LIVE sends so a customer is never
    emailed the same tier twice; dry-run previews never persist and re-evaluate each run.
    """
    summary = {"sent": 0, "dry_run": 0, "skipped_no_email": 0, "skipped_already_sent": 0,
               "failed": 0, "details": []}

    to_send = [it for it in items if it["action"] in _AUTO_SEND_TIERS and not it["requires_approval"]]
    if not to_send:
        return summary

    # Recipient emails come from the synced customer contacts (by ERP contact id, then name).
    contacts = await db.accountingcontact.find_many(
        where={"tenant_id": tenant_id, "email": {"not": None}},
    )
    email_by_extid = {c.external_id: c.email for c in contacts if c.email}
    email_by_name = {c.name.strip().lower(): c.email for c in contacts if c.email and c.name}

    for it in to_send:
        invoice_id, tier = it["invoice_id"], it["action"]
        already = await db.collectionreminder.find_first(
            where={"tenant_id": tenant_id, "invoice_id": invoice_id, "tier": tier, "mode": "live"},
        )
        if already:
            summary["skipped_already_sent"] += 1
            continue

        to_email = email_by_extid.get(it.get("contact_id")) or email_by_name.get(
            (it.get("contact_name") or "").strip().lower()
        )
        if not to_email:
            summary["skipped_no_email"] += 1
            summary["details"].append({"invoice_id": invoice_id, "tier": tier, "status": "no_email"})
            continue

        subject, body = _reminder_message(it)
        try:
            res = await send_via_mailbox(db, tenant_id, to=to_email, subject=subject, body=body)
        except MailError as exc:
            summary["failed"] += 1
            summary["details"].append({"invoice_id": invoice_id, "tier": tier, "status": "failed", "error": str(exc)})
            continue

        if res["mode"] == "live":
            await db.collectionreminder.create(data={
                "tenant_id": tenant_id, "invoice_id": invoice_id, "tier": tier,
                "channel": res["channel"], "to_email": to_email, "mode": "live",
                "status": "sent", "message_id": res.get("message_id") or None, "subject": subject,
            })
            summary["sent"] += 1
            summary["details"].append({"invoice_id": invoice_id, "tier": tier, "status": "sent", "channel": res["channel"]})
        else:
            summary["dry_run"] += 1
            summary["details"].append({"invoice_id": invoice_id, "tier": tier, "status": "dry_run", "channel": res["channel"]})

    return summary


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
            "contact_id": getattr(inv, "contact_id", None),
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
            "Auto reminders are dispatched from the connected mailbox (dry-run unless "
            "emails_live); late fees / write-offs and firmer notices still route to approval."
        ),
    }

    await write_audit_log(
        tenant_id=tenant_id, actor=_ACTOR, action=f"ar_collections:{decision}",
        reasoning_trace=reasoning_trace, model_version=_MODEL_VERSION, execution_id=execution_id,
    )

    # Dispatch auto-approved reminders (dry-run unless emails_live). Audit is written first,
    # above; the send outcome is recorded in its own audit line and in output_data.
    reminders = await _dispatch_auto_reminders(db, tenant_id, items)
    reasoning_trace["reminders"] = reminders
    if any(reminders[k] for k in ("sent", "dry_run", "failed", "skipped_no_email")):
        await write_audit_log(
            tenant_id=tenant_id, actor=_ACTOR, action="ar_collections:reminders_dispatched",
            reasoning_trace={"reminders": reminders}, model_version=_MODEL_VERSION, execution_id=execution_id,
        )

    actions_taken = [
        f"aged {len(outstanding)} outstanding invoice(s); {overdue_count} overdue",
        f"recommended {len(items)} collection action(s)",
    ]
    if reminders["sent"]:
        actions_taken.append(f"sent {reminders['sent']} reminder(s)")
    if reminders["dry_run"]:
        actions_taken.append(f"{reminders['dry_run']} reminder(s) previewed (dry-run - emails not live)")
    if reminders["skipped_no_email"]:
        actions_taken.append(f"{reminders['skipped_no_email']} reminder(s) need a customer email")
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
