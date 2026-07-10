"""
Integration-agnostic ERP write rail. Bills and journal entries are posted to whichever
accounting integration the tenant has connected (QuickBooks or Xero), via ``post_bill`` and
``post_journal_entry``.

Dry-run by default: when ``settings.erp_write_live`` is False nothing is written to the ERP -
the call returns a ``{"mode": "dry_run", ...}`` preview and the Clendan record is left
untouched. Flip ``erp_write_live`` (and connect an accounting integration) to actually post.
Mirrors the payout/mail rails: a live post with no connected ERP raises rather than silently
no-opping.
"""
from __future__ import annotations

from datetime import UTC, datetime

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Providers by capability. QuickBooks and Xero are full GL systems (bills + journals);
# FreshBooks can post AP bills but has no journal-entry API, so it is bill-capable only.
_BILL_PROVIDERS = ("quickbooks", "xero", "freshbooks")
_JOURNAL_PROVIDERS = ("quickbooks", "xero")
_ERP_TYPES = _BILL_PROVIDERS


class ErpWriteError(Exception):
    """Raised when a live ERP write is requested but cannot be fulfilled."""


async def resolve_erp_integration(
    db, tenant_id: str, preferred_id: str | None = None, *, capable: tuple[str, ...] = _ERP_TYPES,
):
    """Return a connected accounting integration for the tenant that supports the requested
    operation, or None. ``capable`` limits the provider types (e.g. journal posting resolves
    only among GL providers). ``connected_at`` is the "actually connected" signal."""
    base = {"tenant_id": tenant_id, "type": {"in": list(capable)}}
    if preferred_id:
        intg = await db.integration.find_first(where={**base, "id": preferred_id})
        if intg:
            return intg
    return await db.integration.find_first(
        where={**base, "connected_at": {"not": None}},
        order={"connected_at": "desc"},
    )


def _lines_payload(lines) -> list[dict]:
    """Normalise JournalEntryLine rows into a provider-neutral line list."""
    out: list[dict] = []
    for ln in lines:
        debit = int(ln.debit_minor or 0)
        credit = int(ln.credit_minor or 0)
        out.append({
            "account_code": ln.account_code,
            "account_name": ln.account_name,
            "posting_type": "Debit" if debit > 0 else "Credit",
            "amount_minor": debit if debit > 0 else credit,
            "description": ln.description or "",
        })
    return out


async def post_bill(
    db, tenant_id: str, bill, *,
    execution_id: str = "", integration=None, preferred_integration_id: str | None = None,
) -> dict:
    """Post a Clendan AccountingBill to the connected ERP as an accounts-payable bill.

    Dry-run (default): returns ``{"mode": "dry_run", "provider": ...}`` and changes nothing.
    Live: creates the bill in the ERP and links ``bill.integration_id``/``external_id`` to it.
    """
    settings = get_settings()
    if not settings.erp_write_live:
        intg = integration or await resolve_erp_integration(db, tenant_id, preferred_integration_id, capable=_BILL_PROVIDERS)
        return {"mode": "dry_run", "provider": intg.type if intg else "none", "bill_id": bill.id, "external_id": None}

    intg = integration or await resolve_erp_integration(db, tenant_id, preferred_integration_id, capable=_BILL_PROVIDERS)
    if intg is None:
        raise ErpWriteError("Live ERP writes are enabled but no accounting integration is connected.")

    if intg.type == "quickbooks":
        from app.integrations.quickbooks.write import write_bill_to_quickbooks
        line_items = bill.raw_data.get("line_items") if isinstance(bill.raw_data, dict) else None
        result = await write_bill_to_quickbooks(
            tenant_id=tenant_id, execution_id=execution_id,
            vendor=bill.contact_name or "Unknown vendor",
            invoice_number=bill.number or bill.id,
            amount_minor=bill.total_cents, currency=bill.currency,
            due_date=bill.due_date.isoformat() if bill.due_date else None,
            line_items=line_items or [{"description": bill.number or "Bill", "amount_minor": bill.total_cents}],
        )
        external_id = result["qb_bill_id"]
    elif intg.type == "xero":
        from app.integrations.xero.write import create_bill as xero_create_bill
        result = await xero_create_bill(db, tenant_id, intg, bill)
        external_id = result["external_id"]
    elif intg.type == "freshbooks":
        from app.integrations.freshbooks.write import create_bill as fb_create_bill
        result = await fb_create_bill(db, tenant_id, intg, bill)
        external_id = result["external_id"]
    else:
        raise ErpWriteError(f"Unsupported ERP integration type: {intg.type!r}")

    await db.accountingbill.update(
        where={"id": bill.id},
        data={"integration_id": intg.id, "external_id": external_id},
    )
    logger.info("erp_bill_posted", extra={"tenant_id": tenant_id, "provider": intg.type, "bill_id": bill.id})
    return {"mode": "live", "provider": intg.type, "bill_id": bill.id, "external_id": external_id}


async def post_journal_entry(
    db, tenant_id: str, entry, *,
    integration=None, preferred_integration_id: str | None = None,
) -> dict:
    """Post a Clendan JournalEntry to the connected ERP as a manual journal.

    Dry-run (default): returns ``{"mode": "dry_run", ...}`` and changes nothing.
    Live: posts the journal, then marks the entry posted (status/posted_at/external_id).
    """
    settings = get_settings()
    if not settings.erp_write_live:
        intg = integration or await resolve_erp_integration(db, tenant_id, preferred_integration_id, capable=_JOURNAL_PROVIDERS)
        return {"mode": "dry_run", "provider": intg.type if intg else "none", "entry_id": entry.id, "external_id": None}

    intg = integration or await resolve_erp_integration(db, tenant_id, preferred_integration_id, capable=_JOURNAL_PROVIDERS)
    if intg is None:
        raise ErpWriteError(
            "Live ERP writes are enabled but no journal-capable integration (QuickBooks or "
            "Xero) is connected. FreshBooks has no journal-entry API."
        )

    lines = await db.journalentryline.find_many(where={"journal_entry_id": entry.id})
    if not lines:
        raise ErpWriteError(f"Journal entry {entry.id} has no lines to post.")
    payload = _lines_payload(lines)

    if intg.type == "quickbooks":
        from app.integrations.quickbooks.write import write_journal_to_quickbooks
        result = await write_journal_to_quickbooks(
            tenant_id=tenant_id, description=entry.description, lines=payload,
        )
        external_id = result["qb_journal_id"]
    elif intg.type == "xero":
        from app.integrations.xero.write import create_manual_journal
        result = await create_manual_journal(db, tenant_id, intg, entry.description, payload)
        external_id = result["external_id"]
    else:
        raise ErpWriteError(f"Unsupported ERP integration type: {intg.type!r}")

    await db.journalentry.update(
        where={"id": entry.id},
        data={"status": "posted", "posted_at": datetime.now(UTC),
              "integration_id": intg.id, "external_id": external_id},
    )
    logger.info("erp_journal_posted", extra={"tenant_id": tenant_id, "provider": intg.type, "entry_id": entry.id})
    return {"mode": "live", "provider": intg.type, "entry_id": entry.id, "external_id": external_id}
