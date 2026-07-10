"""
Xero write client - create AP bills (ACCPAY invoices) and manual journals. Mirrors the
request pattern in client_api.py (circuit breaker + retry). Access token is refreshed via
the shared token manager; the Xero org id (xero_tenant_id) comes from the stored creds.
Called only through app/core/erp_writer.py, which gates every write behind erp_write_live.
"""
import httpx

from app.core.logging import get_logger
from app.integrations.encryption import decrypt_credentials
from app.integrations.token_manager import get_valid_token
from app.integrations.xero.circuit_breaker import _circuit
from app.integrations.xero.client_api import XERO_API_BASE, _retry

logger = get_logger(__name__)


async def _xero_context(db, tenant_id: str, integration) -> tuple[str, str]:
    """Return (access_token, xero_tenant_id). Token is refreshed if near expiry; the org id
    is stable across refreshes so it is read from the stored credentials."""
    access_token = await get_valid_token(integration.id, db)
    creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    xero_tenant_id = creds.get("xero_tenant_id", "")
    if not xero_tenant_id:
        raise ValueError("Xero integration is missing xero_tenant_id")
    return access_token, xero_tenant_id


def _headers(access_token: str, xero_tenant_id: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Xero-Tenant-Id": xero_tenant_id,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


async def create_bill(db, tenant_id: str, integration, bill) -> dict:
    """Create an accounts-payable bill (ACCPAY invoice) in Xero. Returns {external_id}."""
    access_token, xero_tenant_id = await _xero_context(db, tenant_id, integration)

    raw_lines = bill.raw_data.get("line_items") if isinstance(bill.raw_data, dict) else None
    if raw_lines:
        line_items = []
        for li in raw_lines:
            minor = li.get("amount_minor", li.get("total_minor", 0))
            item = {"Description": li.get("description", "") or "Bill", "LineAmount": round(minor / 100, 2)}
            if li.get("account_code"):
                item["AccountCode"] = li["account_code"]
            line_items.append(item)
    else:
        line_items = [{"Description": bill.number or "Bill", "LineAmount": round(bill.total_cents / 100, 2)}]

    payload: dict = {
        "Type": "ACCPAY",
        "Contact": {"Name": bill.contact_name or "Unknown vendor"},
        "LineItems": line_items,
        "Status": "DRAFT",
    }
    if bill.number:
        payload["InvoiceNumber"] = bill.number
    if bill.due_date:
        payload["DueDate"] = bill.due_date.date().isoformat() if hasattr(bill.due_date, "date") else str(bill.due_date)

    async def _call():
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{XERO_API_BASE}/Invoices",
                json={"Invoices": [payload]},
                headers=_headers(access_token, xero_tenant_id),
                timeout=20.0,
            )
            r.raise_for_status()
            return r.json()

    raw = await _circuit.call(_retry, _call)
    inv = (raw.get("Invoices") or [{}])[0]
    external_id = inv.get("InvoiceID", "")
    if not external_id:
        raise ValueError("Xero returned no InvoiceID for the created bill")
    logger.info("xero_bill_created", extra={"tenant_id": tenant_id, "bill_id": bill.id})
    return {"external_id": external_id}


def _manual_journal_lines(lines: list[dict]) -> list[dict]:
    """Map provider-neutral journal lines to Xero JournalLines. Xero LineAmount is signed:
    positive for a debit, negative for a credit."""
    out: list[dict] = []
    for ln in lines:
        amount = round(ln["amount_minor"] / 100, 2)
        signed = amount if ln["posting_type"] == "Debit" else -amount
        jl: dict = {"LineAmount": signed, "AccountCode": ln.get("account_code") or ""}
        if ln.get("description"):
            jl["Description"] = ln["description"]
        out.append(jl)
    return out


async def create_manual_journal(db, tenant_id: str, integration, narration: str, lines: list[dict]) -> dict:
    """Post a manual journal in Xero. ``lines`` are provider-neutral dicts
    {account_code, posting_type, amount_minor, description}. Returns {external_id}."""
    access_token, xero_tenant_id = await _xero_context(db, tenant_id, integration)
    payload = {"Narration": narration, "JournalLines": _manual_journal_lines(lines), "Status": "POSTED"}

    async def _call():
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{XERO_API_BASE}/ManualJournals",
                json={"ManualJournals": [payload]},
                headers=_headers(access_token, xero_tenant_id),
                timeout=20.0,
            )
            r.raise_for_status()
            return r.json()

    raw = await _circuit.call(_retry, _call)
    mj = (raw.get("ManualJournals") or [{}])[0]
    external_id = mj.get("ManualJournalID", "")
    if not external_id:
        raise ValueError("Xero returned no ManualJournalID for the posted journal")
    logger.info("xero_journal_posted", extra={"tenant_id": tenant_id, "line_count": len(lines)})
    return {"external_id": external_id}
