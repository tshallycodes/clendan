"""
QuickBooks persist helpers — idempotent upserts for each accounting entity.
All amounts stored as integer cents. Amounts are converted here; callers pass raw QB dicts.
"""
from datetime import datetime, date, UTC
from typing import Any

from app.core.db import get_db
from app.core.logging import get_logger

logger = get_logger(__name__)

SOURCE = "quickbooks"


def _parse_date(val: str | None) -> datetime | None:
    if not val:
        return None
    try:
        return datetime.strptime(val, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        return None


def _cents(val: Any) -> int:
    try:
        return int(round(float(val or 0) * 100))
    except (TypeError, ValueError):
        return 0


def _today() -> date:
    return datetime.now(UTC).date()


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

async def upsert_invoice(integration_id: str, tenant_id: str, inv: dict) -> None:
    db = get_db()
    balance = float(inv.get("Balance") or 0)
    due_date_str = inv.get("DueDate")
    if balance == 0:
        status = "paid"
    elif due_date_str:
        try:
            due = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            status = "overdue" if due < _today() else "sent"
        except ValueError:
            status = "sent"
    else:
        status = "sent"

    await db.accountinginvoice.upsert(
        where={"integration_id_external_id": {"integration_id": integration_id, "external_id": inv["Id"]}},
        data={
            "create": {
                "tenant_id": tenant_id,
                "integration_id": integration_id,
                "source": SOURCE,
                "external_id": inv["Id"],
                "number": inv.get("DocNumber"),
                "status": status,
                "type": "invoice",
                "contact_name": (inv.get("CustomerRef") or {}).get("name"),
                "currency": (inv.get("CurrencyRef") or {}).get("value", "USD"),
                "total_cents": _cents(inv.get("TotalAmt")),
                "outstanding_cents": _cents(inv.get("Balance")),
                "issue_date": _parse_date(inv.get("TxnDate")),
                "due_date": _parse_date(due_date_str),
            },
            "update": {
                "status": status,
                "contact_name": (inv.get("CustomerRef") or {}).get("name"),
                "currency": (inv.get("CurrencyRef") or {}).get("value", "USD"),
                "total_cents": _cents(inv.get("TotalAmt")),
                "outstanding_cents": _cents(inv.get("Balance")),
                "issue_date": _parse_date(inv.get("TxnDate")),
                "due_date": _parse_date(due_date_str),
            },
        },
    )


# ---------------------------------------------------------------------------
# Bills
# ---------------------------------------------------------------------------

async def upsert_bill(integration_id: str, tenant_id: str, bill: dict) -> None:
    db = get_db()
    balance = float(bill.get("Balance") or 0)
    status = "paid" if balance == 0 else "unpaid"

    await db.accountingbill.upsert(
        where={"integration_id_external_id": {"integration_id": integration_id, "external_id": bill["Id"]}},
        data={
            "create": {
                "tenant_id": tenant_id,
                "integration_id": integration_id,
                "source": SOURCE,
                "external_id": bill["Id"],
                "number": bill.get("DocNumber"),
                "status": status,
                "contact_name": (bill.get("VendorRef") or {}).get("name"),
                "currency": (bill.get("CurrencyRef") or {}).get("value", "USD"),
                "total_cents": _cents(bill.get("TotalAmt")),
                "outstanding_cents": _cents(bill.get("Balance")),
                "issue_date": _parse_date(bill.get("TxnDate")),
                "due_date": _parse_date(bill.get("DueDate")),
            },
            "update": {
                "status": status,
                "contact_name": (bill.get("VendorRef") or {}).get("name"),
                "currency": (bill.get("CurrencyRef") or {}).get("value", "USD"),
                "total_cents": _cents(bill.get("TotalAmt")),
                "outstanding_cents": _cents(bill.get("Balance")),
                "issue_date": _parse_date(bill.get("TxnDate")),
                "due_date": _parse_date(bill.get("DueDate")),
            },
        },
    )


# ---------------------------------------------------------------------------
# Contacts — customers and vendors share the same model
# ---------------------------------------------------------------------------

async def upsert_customer(integration_id: str, tenant_id: str, customer: dict) -> None:
    db = get_db()
    email_obj = customer.get("PrimaryEmailAddr") or {}
    await db.accountingcontact.upsert(
        where={"integration_id_external_id": {"integration_id": integration_id, "external_id": customer["Id"]}},
        data={
            "create": {
                "tenant_id": tenant_id,
                "integration_id": integration_id,
                "source": SOURCE,
                "external_id": customer["Id"],
                "contact_type": "customer",
                "name": customer.get("DisplayName", ""),
                "email": email_obj.get("Address"),
            },
            "update": {
                "contact_type": "customer",
                "name": customer.get("DisplayName", ""),
                "email": email_obj.get("Address"),
            },
        },
    )


async def upsert_vendor(integration_id: str, tenant_id: str, vendor: dict) -> None:
    db = get_db()
    external_id = f"vendor_{vendor['Id']}"
    email_obj = vendor.get("PrimaryEmailAddr") or {}
    await db.accountingcontact.upsert(
        where={"integration_id_external_id": {"integration_id": integration_id, "external_id": external_id}},
        data={
            "create": {
                "tenant_id": tenant_id,
                "integration_id": integration_id,
                "source": SOURCE,
                "external_id": external_id,
                "contact_type": "supplier",
                "name": vendor.get("DisplayName", ""),
                "email": email_obj.get("Address"),
            },
            "update": {
                "contact_type": "supplier",
                "name": vendor.get("DisplayName", ""),
                "email": email_obj.get("Address"),
            },
        },
    )


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------

async def upsert_payment(integration_id: str, tenant_id: str, pmt: dict) -> None:
    db = get_db()
    await db.accountingpayment.upsert(
        where={"integration_id_external_id": {"integration_id": integration_id, "external_id": pmt["Id"]}},
        data={
            "create": {
                "tenant_id": tenant_id,
                "integration_id": integration_id,
                "source": SOURCE,
                "external_id": pmt["Id"],
                "payment_type": "received",
                "amount_cents": _cents(pmt.get("TotalAmt")),
                "currency": (pmt.get("CurrencyRef") or {}).get("value", "USD"),
                "contact_name": (pmt.get("CustomerRef") or {}).get("name"),
                "paid_at": _parse_date(pmt.get("TxnDate")),
            },
            "update": {
                "payment_type": "received",
                "amount_cents": _cents(pmt.get("TotalAmt")),
                "currency": (pmt.get("CurrencyRef") or {}).get("value", "USD"),
                "contact_name": (pmt.get("CustomerRef") or {}).get("name"),
                "paid_at": _parse_date(pmt.get("TxnDate")),
            },
        },
    )


# ---------------------------------------------------------------------------
# Expenses (Purchases)
# ---------------------------------------------------------------------------

async def upsert_expense(integration_id: str, tenant_id: str, purchase: dict) -> None:
    db = get_db()
    line_items = purchase.get("Line") or []
    account_ref = {}
    if line_items:
        detail = line_items[0].get("AccountBasedExpenseLineDetail") or {}
        account_ref = detail.get("AccountRef") or {}

    await db.accountingexpense.upsert(
        where={"integration_id_external_id": {"integration_id": integration_id, "external_id": purchase["Id"]}},
        data={
            "create": {
                "tenant_id": tenant_id,
                "integration_id": integration_id,
                "source": SOURCE,
                "external_id": purchase["Id"],
                "amount_cents": _cents(purchase.get("TotalAmt")),
                "description": purchase.get("PrivateNote") or "",
                "contact_name": (purchase.get("EntityRef") or {}).get("name"),
                "expense_date": _parse_date(purchase.get("TxnDate")),
                "account_code": account_ref.get("value"),
            },
            "update": {
                "amount_cents": _cents(purchase.get("TotalAmt")),
                "description": purchase.get("PrivateNote") or "",
                "contact_name": (purchase.get("EntityRef") or {}).get("name"),
                "expense_date": _parse_date(purchase.get("TxnDate")),
                "account_code": account_ref.get("value"),
            },
        },
    )


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

async def upsert_account(integration_id: str, tenant_id: str, acct: dict) -> None:
    db = get_db()
    await db.accountingaccount.upsert(
        where={"integration_id_external_id": {"integration_id": integration_id, "external_id": acct["Id"]}},
        data={
            "create": {
                "tenant_id": tenant_id,
                "integration_id": integration_id,
                "source": SOURCE,
                "external_id": acct["Id"],
                "code": acct.get("AcctNum"),
                "name": acct.get("Name", ""),
                "account_type": acct.get("AccountType", ""),
            },
            "update": {
                "code": acct.get("AcctNum"),
                "name": acct.get("Name", ""),
                "account_type": acct.get("AccountType", ""),
            },
        },
    )


# ---------------------------------------------------------------------------
# Tax rates (TaxCodes)
# ---------------------------------------------------------------------------

async def upsert_tax_rate(integration_id: str, tenant_id: str, tax_code: dict) -> None:
    db = get_db()
    # TaxCodes don't expose rate directly — derive tax_type from first rate ref name if present
    config_details = tax_code.get("TaxCodeConfigDetail") or {}
    tax_rate_refs = config_details.get("TaxRateRef") or []
    tax_type: str | None = None
    if isinstance(tax_rate_refs, list) and tax_rate_refs:
        tax_type = tax_rate_refs[0].get("name")
    elif isinstance(tax_rate_refs, dict):
        tax_type = tax_rate_refs.get("name")

    await db.accountingtaxrate.upsert(
        where={"integration_id_external_id": {"integration_id": integration_id, "external_id": tax_code["Id"]}},
        data={
            "create": {
                "tenant_id": tenant_id,
                "integration_id": integration_id,
                "source": SOURCE,
                "external_id": tax_code["Id"],
                "name": tax_code.get("Name", ""),
                "rate_pct": 0.0,
                "tax_type": tax_type,
            },
            "update": {
                "name": tax_code.get("Name", ""),
                "rate_pct": 0.0,
                "tax_type": tax_type,
            },
        },
    )


# ---------------------------------------------------------------------------
# Credit notes (CreditMemos)
# ---------------------------------------------------------------------------

async def upsert_credit_note(integration_id: str, tenant_id: str, memo: dict) -> None:
    db = get_db()
    balance = float(memo.get("Balance") or 0)
    status = "open" if balance > 0 else "closed"

    await db.accountingcreditnote.upsert(
        where={"integration_id_external_id": {"integration_id": integration_id, "external_id": memo["Id"]}},
        data={
            "create": {
                "tenant_id": tenant_id,
                "integration_id": integration_id,
                "source": SOURCE,
                "external_id": memo["Id"],
                "number": memo.get("DocNumber"),
                "status": status,
                "contact_name": (memo.get("CustomerRef") or {}).get("name"),
                "currency": (memo.get("CurrencyRef") or {}).get("value", "USD"),
                "total_cents": _cents(memo.get("TotalAmt")),
                "remaining_cents": _cents(memo.get("Balance")),
                "issue_date": _parse_date(memo.get("TxnDate")),
            },
            "update": {
                "status": status,
                "contact_name": (memo.get("CustomerRef") or {}).get("name"),
                "currency": (memo.get("CurrencyRef") or {}).get("value", "USD"),
                "total_cents": _cents(memo.get("TotalAmt")),
                "remaining_cents": _cents(memo.get("Balance")),
                "issue_date": _parse_date(memo.get("TxnDate")),
            },
        },
    )
