"""
Governed agent actions: the propose -> confirm -> execute spine for anything the chat agent
does that changes state.

The agent never mutates directly. It calls ``propose_action`` (which persists an AgentAction
in status "proposed" and returns a preview for a confirm card in the UI). Only when the user
confirms does ``execute_action`` run it - through the same governed path as any other trigger
(``enqueue_for_tool_type``), never by a tool calling another tool. Money actions reuse this
with ``capability="money"`` behind a details-verified confirmation (added in a later phase).

Every proposal expires (ACTION_TTL_SECONDS) so a stale, un-confirmed action can never fire.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from prisma import Json as PrismaJson

from app.audit.logger import write_audit_log
from app.core.logging import get_logger

logger = get_logger(__name__)

ACTION_TTL_SECONDS = 900  # a proposed action must be confirmed within 15 minutes
PREPARE_PAYMENT_WINDOW_DAYS = 7  # a prepared (scheduled) payment awaits human release this long
_MODEL_VERSION = "agent_actions/1.0"

# kind -> capability. Read actions never reach here (they return data directly); everything
# routed through propose/confirm is a state change. A "money" action PREPARES only: it records
# payment intent for the authorised human to release - there is no disbursement path
# (see app/core/payouts.py), so a money action can never move funds.
_ACTION_CAPABILITY = {
    "run_automation": "write",
    "create_bill": "write",
    "prepare_payment": "money",
}


class AgentActionError(Exception):
    """Raised when a proposal cannot be built or executed."""


async def propose_action(db, tenant_id: str, *, kind: str, params: dict, proposed_by: str | None) -> dict:
    """Validate and persist a proposed action. Returns the confirm-card payload. Does NOT
    change any external state - it only records intent for the user to confirm."""
    if kind not in _ACTION_CAPABILITY:
        raise AgentActionError(f"Unknown action kind: {kind!r}")

    preview, norm_params = await _build_preview(db, tenant_id, kind, params)
    now = datetime.now(UTC)
    action = await db.agentaction.create(
        data={
            "tenant_id": tenant_id,
            "kind": kind,
            "capability": _ACTION_CAPABILITY[kind],
            "params": norm_params,
            "preview": preview,
            "status": "proposed",
            "proposed_by": proposed_by,
            "expires_at": now + timedelta(seconds=ACTION_TTL_SECONDS),
        }
    )
    payload = {
        "action_id": action.id,
        "kind": kind,
        "capability": action.capability,
        "preview": preview,
        "requires_confirmation": True,
        "expires_at": action.expires_at.isoformat(),
    }
    # Money proposals carry the payee / account / amount + account-changed flag so the UI can
    # render a details-verified confirmation sheet before the human releases the payment.
    if action.capability == "money":
        payload["details"] = _money_details(norm_params)
    return payload


async def execute_action(db, tenant_id: str, action_id: str, *, confirmed_by: str | None) -> dict:
    """Execute a previously-proposed action after the user confirms it. Idempotent: a second
    confirm of the same action returns the same execution rather than firing twice."""
    action = await db.agentaction.find_first(where={"id": action_id, "tenant_id": tenant_id})
    if action is None:
        raise AgentActionError("Action not found")
    if action.status == "executed":
        return {"executed": True, "action_id": action.id, "execution_id": action.execution_id, "idempotent": True}
    if action.status != "proposed":
        raise AgentActionError(f"Action is {action.status}, cannot execute")
    if action.expires_at <= datetime.now(UTC):
        await db.agentaction.update(where={"id": action.id}, data={"status": "expired"})
        raise AgentActionError("Action expired - ask again to propose a fresh one")

    execution_id = await _execute_by_kind(db, tenant_id, action, confirmed_by)

    await db.agentaction.update(
        where={"id": action.id},
        data={"status": "executed", "confirmed_by": confirmed_by,
              "confirmed_at": datetime.now(UTC), "execution_id": execution_id},
    )
    await write_audit_log(
        tenant_id=tenant_id, actor=f"agent:{confirmed_by or 'unknown'}",
        action=f"agent_action:{action.kind}",
        reasoning_trace={"action_id": action.id, "params": action.params, "execution_id": execution_id},
        model_version=_MODEL_VERSION, execution_id=execution_id,
    )
    return {"executed": True, "action_id": action.id, "execution_id": execution_id}


async def cancel_action(db, tenant_id: str, action_id: str) -> dict:
    """Cancel a proposed action the user declined."""
    action = await db.agentaction.find_first(where={"id": action_id, "tenant_id": tenant_id})
    if action is None:
        raise AgentActionError("Action not found")
    if action.status == "proposed":
        await db.agentaction.update(where={"id": action.id}, data={"status": "cancelled"})
    return {"cancelled": True, "action_id": action_id}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_minor(amount_minor: int, currency: str) -> str:
    """Human amount from integer minor units, e.g. (12345, 'GBP') -> 'GBP 123.45'."""
    whole, cents = divmod(abs(int(amount_minor)), 100)
    sign = "-" if int(amount_minor) < 0 else ""
    return f"{sign}{currency} {whole}.{cents:02d}"


def _normalise_vendor_ref(name: str) -> str:
    """Fallback vendor key when there is no ERP contact id: whitespace-collapsed, lower-cased."""
    return " ".join((name or "").split()).lower()


def _parse_iso_date(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _money_details(norm_params: dict) -> dict:
    """The payee / account / amount + change flag a money proposal's confirm sheet renders."""
    return {
        "payee": norm_params.get("payee"),
        "account_identifier": norm_params.get("account_identifier"),
        "amount_minor": norm_params.get("amount_minor"),
        "currency": norm_params.get("currency"),
        "account_changed": bool(norm_params.get("account_changed")),
    }


# ---------------------------------------------------------------------------
# Per-kind preview + execution
# ---------------------------------------------------------------------------

async def _build_preview(db, tenant_id: str, kind: str, params: dict) -> tuple[str, dict]:
    """Return (human preview, normalised params) for a proposal, validating referenced records."""
    if kind == "run_automation":
        tool_type = str(params.get("tool_type") or "").strip()
        if not tool_type:
            raise AgentActionError("tool_type is required")
        tool = await db.tool.find_first(where={"tenant_id": tenant_id, "type": tool_type})
        if tool is None:
            raise AgentActionError(f"No '{tool_type}' automation is deployed")
        if tool.status != "active":
            raise AgentActionError(f"The '{tool_type}' automation is paused - deploy it first")
        return (f"Run the {tool_type} automation now.", {"tool_id": tool.id, "tool_type": tool_type})

    if kind == "create_bill":
        vendor = str(params.get("vendor") or "").strip()
        if not vendor:
            raise AgentActionError("vendor is required")
        amount_minor = int(params.get("amount_minor") or 0)
        if amount_minor <= 0:
            raise AgentActionError("amount_minor must be a positive integer (minor units)")
        currency = (str(params.get("currency") or "GBP").strip() or "GBP").upper()
        number = str(params.get("number") or "").strip() or None
        due_date = str(params.get("due_date") or "").strip() or None
        preview = f"Create a bill for {vendor}: {_format_minor(amount_minor, currency)}"
        norm = {
            "vendor": vendor,
            "amount_minor": amount_minor,
            "currency": currency,
            "number": number,
            "due_date": due_date,
        }
        return preview, norm

    if kind == "prepare_payment":
        bill_id = str(params.get("bill_id") or "").strip() or None
        if bill_id:
            bill = await db.accountingbill.find_first(where={"id": bill_id, "tenant_id": tenant_id})
            if bill is None:
                raise AgentActionError("Bill not found")
            payee = (bill.contact_name or "").strip() or "Unknown vendor"
            vendor_ref = (getattr(bill, "contact_id", None) or "").strip() or _normalise_vendor_ref(payee)
            amount_minor = int(bill.outstanding_cents or 0) or int(bill.total_cents or 0)
            currency = (bill.currency or "GBP").strip().upper()
        else:
            payee = str(params.get("vendor") or "").strip()
            if not payee:
                raise AgentActionError("vendor is required when no bill_id is given")
            amount_minor = int(params.get("amount_minor") or 0)
            currency = (str(params.get("currency") or "GBP").strip() or "GBP").upper()
            vendor_ref = _normalise_vendor_ref(payee)
        if amount_minor <= 0:
            raise AgentActionError("amount_minor must be a positive integer (minor units)")

        # Account-change detection: the confirmed destination vs the account we last paid.
        target_account = str(params.get("account_identifier") or "").strip()
        stored = await db.vendorbankdetail.find_first(
            where={"tenant_id": tenant_id, "vendor_ref": vendor_ref}
        )
        if not target_account:
            if stored and (stored.account_identifier or "").strip():
                target_account = stored.account_identifier
            else:
                raise AgentActionError(
                    "No bank account on file for this supplier - provide an account to pay to"
                )
        account_changed = (stored is None) or ((stored.account_identifier or "") != target_account)

        preview = f"Prepare a payment to {payee}: {_format_minor(amount_minor, currency)}"
        if account_changed:
            preview += " - bank account changed since the last payment to this supplier"
        norm = {
            "bill_id": bill_id,
            "vendor_ref": vendor_ref,
            "payee": payee,
            "amount_minor": amount_minor,
            "currency": currency,
            "account_identifier": target_account,
            "account_changed": account_changed,
        }
        return preview, norm

    raise AgentActionError(f"Unknown action kind: {kind!r}")


async def _execute_by_kind(db, tenant_id: str, action, confirmed_by: str | None) -> str | None:
    """Execute the action through the governed path. Returns the execution id when the action
    dispatches a tool run, or None for a direct write/prepare (which audits + mutates inline)."""
    if action.kind == "create_bill":
        return await _execute_create_bill(db, tenant_id, action, confirmed_by)
    if action.kind == "prepare_payment":
        return await _execute_prepare_payment(db, tenant_id, action, confirmed_by)
    if action.kind == "run_automation":
        params = action.params if isinstance(action.params, dict) else {}
        tool = await db.tool.find_first(where={"id": params.get("tool_id"), "tenant_id": tenant_id})
        if tool is None or tool.status != "active":
            raise AgentActionError("Automation is no longer active")

        # Idempotency: one execution per confirmed action (unique tenant_id + input_ref).
        input_ref = f"agent:{action.id}"
        existing = await db.execution.find_first(
            where={"tenant_id": tenant_id, "tool_id": tool.id, "input_ref": input_ref}
        )
        if existing:
            return existing.id

        execution = await db.execution.create(
            data={"tenant_id": tenant_id, "tool_id": tool.id, "input_ref": input_ref,
                  "decision": "pending", "confidence": 0.0, "status": "queued"}
        )
        from app.core.dispatch import enqueue_for_tool_type
        from app.queue.pool import get_queue_pool
        pool = await get_queue_pool()
        await enqueue_for_tool_type(
            pool=pool, tool_type=tool.type, execution_id=execution.id,
            tenant_id=tenant_id, tool_id=tool.id, payload={},
        )
        return execution.id
    raise AgentActionError(f"Unknown action kind: {action.kind!r}")


async def _execute_create_bill(db, tenant_id: str, action, confirmed_by: str | None) -> None:
    """Create a native AccountingBill (source="invoice", no ERP integration) and post it to the
    connected ERP via the governed write rail. post_bill is dry-run unless erp_write_live, and
    never a silent no-op. Audit-first: the bill is not written until the audit entry is recorded."""
    params = action.params if isinstance(action.params, dict) else {}
    actor = f"agent:{confirmed_by or 'unknown'}"
    amount = int(params.get("amount_minor") or 0)
    number = params.get("number")
    external_id = number or f"agent:{action.id}"

    # Audit BEFORE the write - if the audit fails, nothing is created.
    await write_audit_log(
        tenant_id=tenant_id, actor=actor, action="agent_action:create_bill",
        reasoning_trace={"vendor": params.get("vendor"), "amount_minor": amount,
                         "currency": params.get("currency"), "number": number,
                         "external_id": external_id},
        model_version=_MODEL_VERSION,
    )

    # Idempotency: dedupe on (tenant, source, external_id), the same key document_intelligence uses.
    bill = await db.accountingbill.find_first(
        where={"tenant_id": tenant_id, "source": "invoice", "external_id": external_id}
    )
    if bill is None:
        bill = await db.accountingbill.create(data={
            "tenant_id": tenant_id,
            "source": "invoice",
            "external_id": external_id,
            "number": number,
            "status": "open",
            "contact_name": params.get("vendor"),
            "currency": params.get("currency") or "GBP",
            "total_cents": amount,
            "outstanding_cents": amount,
            "due_date": _parse_iso_date(params.get("due_date")),
            "raw_data": PrismaJson({"origin": "agent_action", "action_id": action.id}),
        })

    from app.core.erp_writer import post_bill
    await post_bill(db, tenant_id, bill)
    return None


async def _execute_prepare_payment(db, tenant_id: str, action, confirmed_by: str | None) -> None:
    """PREPARE a payment - never disburse. Records intent as a SCHEDULED PaymentRun the human
    releases in the bank/ERP, and remembers the confirmed destination account (VendorBankDetail)
    for next time's change-detection. There is deliberately no disbursement call here (see
    app/core/payouts.py): this path cannot move money. Audit-first before any mutation."""
    params = action.params if isinstance(action.params, dict) else {}
    actor = f"agent:{confirmed_by or 'unknown'}"
    vendor_ref = str(params.get("vendor_ref") or "")
    amount = int(params.get("amount_minor") or 0)
    currency = str(params.get("currency") or "GBP")
    account_identifier = str(params.get("account_identifier") or "")
    bill_id = params.get("bill_id")

    # Audit BEFORE preparing. mode="prepare_only" - this records intent, it does not pay.
    await write_audit_log(
        tenant_id=tenant_id, actor=actor, action="agent_action:prepare_payment",
        reasoning_trace={"payee": params.get("payee"), "amount_minor": amount,
                         "currency": currency, "vendor_ref": vendor_ref,
                         "account_changed": bool(params.get("account_changed")),
                         "bill_id": bill_id, "mode": "prepare_only"},
        model_version=_MODEL_VERSION,
    )

    # Remember the confirmed destination account so a later change is flagged.
    await db.vendorbankdetail.upsert(
        where={"tenant_id_vendor_ref": {"tenant_id": tenant_id, "vendor_ref": vendor_ref}},
        data={
            "create": {"tenant_id": tenant_id, "vendor_ref": vendor_ref,
                       "account_identifier": account_identifier, "currency": currency},
            "update": {"account_identifier": account_identifier, "currency": currency},
        },
    )

    # Record intent as a SCHEDULED run - the authorised human releases it where the money lives.
    # No disbursement rail is touched; Clendan never moves the funds.
    bill_ids = [bill_id] if bill_id else []
    await db.paymentrun.create(data={
        "tenant_id": tenant_id,
        "execution_id": None,
        "status": "scheduled",
        "scheduled_for": datetime.now(UTC) + timedelta(days=PREPARE_PAYMENT_WINDOW_DAYS),
        "bill_count": len(bill_ids),
        "total_amount_cents": amount,
        "currency": currency,
        "bill_ids": bill_ids,
    })
    return None
