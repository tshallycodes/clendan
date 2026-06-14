"""
Xero persist helpers — upsert each entity type into the DB.
Called by sync.py. Each function accepts the prisma db client, integration_id,
tenant_id, and the raw list returned by client_api.
All amounts stored as integer cents (float * 100, rounded to int).
"""
import re
from datetime import datetime, timezone, UTC
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

_XERO_TICK_RE = re.compile(r"/Date\((\d+)([+-]\d+)?\)/")


def _parse_xero_date(value: Optional[str]) -> Optional[datetime]:
    """
    Parses a Xero date string into a UTC-aware datetime.
    Handles:
      - "/Date(1234567890000+0000)/" — millisecond epoch
      - "2023-01-15" or "2023-01-15T00:00:00" — ISO 8601
    Returns None if value is None / empty / unparseable.
    """
    if not value:
        return None
    m = _XERO_TICK_RE.match(value)
    if m:
        ms = int(m.group(1))
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None


def _cents(value) -> int:
    """Convert a float/string amount to integer cents. Defaults to 0."""
    try:
        return round(float(value) * 100)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Invoice status mapping
# ---------------------------------------------------------------------------

_INVOICE_STATUS_MAP = {
    "AUTHORISED": "sent",
    "PAID": "paid",
    "DRAFT": "draft",
    "VOIDED": "void",
    "DELETED": "void",
    "SUBMITTED": "draft",
}


def _map_invoice_status(raw: str) -> str:
    return _INVOICE_STATUS_MAP.get(raw, "draft")


# ---------------------------------------------------------------------------
# Upsert helpers
# ---------------------------------------------------------------------------

async def upsert_invoices(db, integration_id: str, tenant_id: str, records: list) -> int:
    """Upsert AR invoices into AccountingInvoice. Returns count upserted."""
    count = 0
    for inv in records:
        external_id = str(inv.get("InvoiceID", ""))
        if not external_id:
            continue
        payload = {
            "integration_id": integration_id,
            "tenant_id": tenant_id,
            "external_id": external_id,
            "number": inv.get("InvoiceNumber") or "",
            "status": _map_invoice_status(inv.get("Status", "")),
            "contact_name": (inv.get("Contact") or {}).get("Name") or "",
            "currency": inv.get("CurrencyCode") or "",
            "total_cents": _cents(inv.get("Total", 0)),
            "outstanding_cents": _cents(inv.get("AmountDue", 0)),
            "tax_cents": _cents(inv.get("TotalTax", 0)),
            "subtotal_cents": _cents(inv.get("SubTotal", 0)),
            "due_date": _parse_xero_date(inv.get("DueDateString")),
            "issue_date": _parse_xero_date(inv.get("DateString")),
            "type": "invoice",
        }
        try:
            await db.accountinginvoice.upsert(
                where={"integration_id_external_id": {
                    "integration_id": integration_id,
                    "external_id": external_id,
                }},
                data={"create": payload, "update": {k: v for k, v in payload.items()
                                                     if k not in ("integration_id", "tenant_id", "external_id")}},
            )
            count += 1
        except Exception as exc:
            logger.error("xero_upsert_invoice_failed external_id=%s: %s", external_id, type(exc).__name__)
    return count


async def upsert_bills(db, integration_id: str, tenant_id: str, records: list) -> int:
    """Upsert AP bills into AccountingBill. Returns count upserted."""
    count = 0
    for bill in records:
        external_id = str(bill.get("InvoiceID", ""))
        if not external_id:
            continue
        payload = {
            "integration_id": integration_id,
            "tenant_id": tenant_id,
            "external_id": external_id,
            "number": bill.get("InvoiceNumber") or "",
            "status": _map_invoice_status(bill.get("Status", "")),
            "contact_name": (bill.get("Contact") or {}).get("Name") or "",
            "currency": bill.get("CurrencyCode") or "",
            "total_cents": _cents(bill.get("Total", 0)),
            "outstanding_cents": _cents(bill.get("AmountDue", 0)),
            "tax_cents": _cents(bill.get("TotalTax", 0)),
            "subtotal_cents": _cents(bill.get("SubTotal", 0)),
            "due_date": _parse_xero_date(bill.get("DueDateString")),
            "issue_date": _parse_xero_date(bill.get("DateString")),
            "type": "bill",
        }
        try:
            await db.accountingbill.upsert(
                where={"integration_id_external_id": {
                    "integration_id": integration_id,
                    "external_id": external_id,
                }},
                data={"create": payload, "update": {k: v for k, v in payload.items()
                                                     if k not in ("integration_id", "tenant_id", "external_id")}},
            )
            count += 1
        except Exception as exc:
            logger.error("xero_upsert_bill_failed external_id=%s: %s", external_id, type(exc).__name__)
    return count


async def upsert_contacts(db, integration_id: str, tenant_id: str, records: list) -> int:
    """Upsert contacts into AccountingContact. Returns count upserted."""
    count = 0
    for contact in records:
        external_id = str(contact.get("ContactID", ""))
        if not external_id:
            continue
        is_customer = bool(contact.get("IsCustomer", False))
        is_supplier = bool(contact.get("IsSupplier", False))
        if is_customer and is_supplier:
            contact_type = "both"
        elif is_customer:
            contact_type = "customer"
        else:
            contact_type = "supplier"
        payload = {
            "integration_id": integration_id,
            "tenant_id": tenant_id,
            "external_id": external_id,
            "name": contact.get("Name") or "",
            "email": contact.get("EmailAddress") or "",
            "contact_type": contact_type,
        }
        try:
            await db.accountingcontact.upsert(
                where={"integration_id_external_id": {
                    "integration_id": integration_id,
                    "external_id": external_id,
                }},
                data={"create": payload, "update": {k: v for k, v in payload.items()
                                                     if k not in ("integration_id", "tenant_id", "external_id")}},
            )
            count += 1
        except Exception as exc:
            logger.error("xero_upsert_contact_failed external_id=%s: %s", external_id, type(exc).__name__)
    return count


async def upsert_payments(db, integration_id: str, tenant_id: str, records: list) -> int:
    """Upsert payments into AccountingPayment. Returns count upserted."""
    count = 0
    for pmt in records:
        external_id = str(pmt.get("PaymentID", ""))
        if not external_id:
            continue
        payload = {
            "integration_id": integration_id,
            "tenant_id": tenant_id,
            "external_id": external_id,
            "amount_cents": _cents(pmt.get("Amount", 0)),
            "currency": pmt.get("CurrencyCode") or "",
            "reference": pmt.get("Reference") or "",
            "paid_at": _parse_xero_date(pmt.get("DateString")),
            "payment_type": "received" if pmt.get("IsReconciled") else "made",
        }
        try:
            await db.accountingpayment.upsert(
                where={"integration_id_external_id": {
                    "integration_id": integration_id,
                    "external_id": external_id,
                }},
                data={"create": payload, "update": {k: v for k, v in payload.items()
                                                     if k not in ("integration_id", "tenant_id", "external_id")}},
            )
            count += 1
        except Exception as exc:
            logger.error("xero_upsert_payment_failed external_id=%s: %s", external_id, type(exc).__name__)
    return count


async def upsert_expenses(db, integration_id: str, tenant_id: str, records: list) -> int:
    """Upsert SPEND BankTransactions into AccountingExpense. Returns count upserted."""
    count = 0
    for txn in records:
        external_id = str(txn.get("BankTransactionID", ""))
        if not external_id:
            continue
        payload = {
            "integration_id": integration_id,
            "tenant_id": tenant_id,
            "external_id": external_id,
            "amount_cents": _cents(txn.get("Total", 0)),
            "description": txn.get("Reference") or "",
            "contact_name": (txn.get("Contact") or {}).get("Name") or "",
            "expense_date": _parse_xero_date(txn.get("DateString")),
            "account_code": (txn.get("BankAccount") or {}).get("Code") or "",
        }
        try:
            await db.accountingexpense.upsert(
                where={"integration_id_external_id": {
                    "integration_id": integration_id,
                    "external_id": external_id,
                }},
                data={"create": payload, "update": {k: v for k, v in payload.items()
                                                     if k not in ("integration_id", "tenant_id", "external_id")}},
            )
            count += 1
        except Exception as exc:
            logger.error("xero_upsert_expense_failed external_id=%s: %s", external_id, type(exc).__name__)
    return count


async def upsert_accounts(db, integration_id: str, tenant_id: str, records: list) -> int:
    """Upsert chart-of-accounts entries into AccountingAccount. Returns count upserted."""
    count = 0
    for acct in records:
        external_id = str(acct.get("AccountID", ""))
        if not external_id:
            continue
        payload = {
            "integration_id": integration_id,
            "tenant_id": tenant_id,
            "external_id": external_id,
            "code": acct.get("Code") or "",
            "name": acct.get("Name") or "",
            "account_type": acct.get("Type") or "",
            "description": acct.get("Description") or "",
        }
        try:
            await db.accountingaccount.upsert(
                where={"integration_id_external_id": {
                    "integration_id": integration_id,
                    "external_id": external_id,
                }},
                data={"create": payload, "update": {k: v for k, v in payload.items()
                                                     if k not in ("integration_id", "tenant_id", "external_id")}},
            )
            count += 1
        except Exception as exc:
            logger.error("xero_upsert_account_failed external_id=%s: %s", external_id, type(exc).__name__)
    return count


async def upsert_credit_notes(db, integration_id: str, tenant_id: str, records: list) -> int:
    """Upsert credit notes into AccountingCreditNote. Returns count upserted."""
    count = 0
    for cn in records:
        external_id = str(cn.get("CreditNoteID", ""))
        if not external_id:
            continue
        payload = {
            "integration_id": integration_id,
            "tenant_id": tenant_id,
            "external_id": external_id,
            "number": cn.get("CreditNoteNumber") or "",
            "status": _map_invoice_status(cn.get("Status", "")),
            "contact_name": (cn.get("Contact") or {}).get("Name") or "",
            "total_cents": _cents(cn.get("Total", 0)),
            "remaining_cents": _cents(cn.get("RemainingCredit", 0)),
            "issue_date": _parse_xero_date(cn.get("DateString")),
        }
        try:
            await db.accountingcreditnote.upsert(
                where={"integration_id_external_id": {
                    "integration_id": integration_id,
                    "external_id": external_id,
                }},
                data={"create": payload, "update": {k: v for k, v in payload.items()
                                                     if k not in ("integration_id", "tenant_id", "external_id")}},
            )
            count += 1
        except Exception as exc:
            logger.error("xero_upsert_credit_note_failed external_id=%s: %s", external_id, type(exc).__name__)
    return count


async def upsert_tax_rates(db, integration_id: str, tenant_id: str, records: list) -> int:
    """Upsert tax rates into AccountingTaxRate. Returns count upserted."""
    count = 0
    for tr in records:
        external_id = str(tr.get("TaxType", ""))
        if not external_id:
            continue
        payload = {
            "integration_id": integration_id,
            "tenant_id": tenant_id,
            "external_id": external_id,
            "name": tr.get("Name") or "",
            "rate_pct": float(tr.get("EffectiveRate", 0) or 0),
            "tax_type": tr.get("TaxType") or "",
        }
        try:
            await db.accountingtaxrate.upsert(
                where={"integration_id_external_id": {
                    "integration_id": integration_id,
                    "external_id": external_id,
                }},
                data={"create": payload, "update": {k: v for k, v in payload.items()
                                                     if k not in ("integration_id", "tenant_id", "external_id")}},
            )
            count += 1
        except Exception as exc:
            logger.error("xero_upsert_tax_rate_failed external_id=%s: %s", external_id, type(exc).__name__)
    return count
