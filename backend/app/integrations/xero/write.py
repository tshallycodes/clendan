"""
Xero bill write — creates an ACCPAY invoice for a document pushed from Document Intelligence.
"""
import asyncio
import random

import httpx

from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.encryption import decrypt_credentials
from app.integrations.xero.circuit_breaker import _circuit

logger = get_logger(__name__)

XERO_API_BASE = "https://api.xero.com/api.xro/2.0"
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0


async def _retry(fn, *args, **kwargs):
    last_exc = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            return await fn(*args, **kwargs)
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.NetworkError) as exc:
            last_exc = exc
            if attempt < MAX_ATTEMPTS - 1:
                wait = BACKOFF_SECONDS * (2 ** attempt) + random.uniform(0, 0.5)
                logger.warning(
                    "xero_write_retry attempt=%d/%d retry_in=%.1fs",
                    attempt + 1, MAX_ATTEMPTS, wait,
                )
                await asyncio.sleep(wait)
    raise last_exc


async def create_bill(
    tenant_id: str,
    vendor: str,
    invoice_number: str,
    amount_minor: int,
    currency: str,
    due_date: str | None,
) -> dict:
    """
    Creates an ACCPAY invoice (bill) in Xero for the given tenant.
    Decrypts credentials from DB. Returns {"xero_invoice_id": str}.
    Raises ValueError if no connected integration or credentials incomplete.
    """
    db = get_db()
    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "xero", "status": "connected"}
    )
    if not integration:
        raise ValueError(f"No connected Xero integration for tenant {tenant_id}")

    creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    access_token: str = creds.get("access_token", "")
    xero_tenant_id: str = creds.get("xero_tenant_id", "")

    if not access_token or not xero_tenant_id:
        raise ValueError("Xero credentials missing access_token or xero_tenant_id")

    amount_decimal = round(amount_minor / 100.0, 2)
    invoice_payload: dict = {
        "Type": "ACCPAY",
        "Contact": {"Name": vendor},
        "InvoiceNumber": invoice_number,
        "CurrencyCode": currency.upper(),
        "Status": "DRAFT",
        "LineItems": [
            {
                "Description": f"Invoice {invoice_number} from {vendor}",
                "Quantity": 1.0,
                "UnitAmount": amount_decimal,
                "AccountCode": "200",
            }
        ],
    }
    if due_date:
        invoice_payload["DueDate"] = due_date

    async def _call():
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{XERO_API_BASE}/Invoices",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Xero-Tenant-Id": xero_tenant_id,
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json={"Invoices": [invoice_payload]},
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()

    raw = await _circuit.call(_retry, _call)
    invoices = raw.get("Invoices", [])
    if not invoices:
        raise ValueError("Xero returned empty Invoices array — bill not created")

    xero_invoice_id: str = invoices[0].get("InvoiceID", "")
    logger.info(
        "xero_bill_created",
        extra={
            "tenant_id": tenant_id,
            "xero_invoice_id": xero_invoice_id,
            "invoice_number": invoice_number,
        },
    )
    return {"xero_invoice_id": xero_invoice_id}
