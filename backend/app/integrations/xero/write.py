"""
Xero bill write — creates an ACCPAY invoice for a document pushed from Document Intelligence.
"""
import asyncio
import random
from datetime import UTC, datetime

import httpx

from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.encryption import decrypt_credentials, encrypt_credentials
from app.integrations.xero.circuit_breaker import _circuit
from app.integrations.xero.client_auth import refresh_xero_token

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
    logger.info("xero_create_bill_start", extra={
        "tenant_id": tenant_id, "vendor": vendor,
        "invoice_number": invoice_number, "amount_minor": amount_minor,
        "currency": currency, "due_date": due_date,
    })

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "xero", "status": "connected"}
    )
    if not integration:
        logger.error("xero_no_connected_integration", extra={"tenant_id": tenant_id})
        raise ValueError(f"No connected Xero integration for tenant {tenant_id}")

    logger.info("xero_integration_found", extra={
        "tenant_id": tenant_id, "integration_id": integration.id,
    })

    creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    access_token: str = creds.get("access_token", "")
    xero_tenant_id: str = creds.get("xero_tenant_id", "")

    token_expiry_at = creds.get("token_expiry_at")
    if token_expiry_at:
        try:
            if datetime.fromisoformat(token_expiry_at) <= datetime.now(UTC):
                logger.info("xero_write_token_expired_refreshing", extra={"tenant_id": tenant_id})
                new_tokens = await refresh_xero_token(creds.get("refresh_token", ""))
                creds = {**creds, **new_tokens}
                access_token = new_tokens["access_token"]
                await db.integration.update(
                    where={"id": integration.id},
                    data={"encrypted_credentials": encrypt_credentials(creds, tenant_id)},
                )
        except Exception as exc:
            logger.error("xero_write_token_refresh_failed", extra={"tenant_id": tenant_id, "error": type(exc).__name__})

    logger.info("xero_credentials_check", extra={
        "tenant_id": tenant_id,
        "has_access_token": bool(access_token),
        "has_xero_tenant_id": bool(xero_tenant_id),
        "cred_keys": list(creds.keys()),
    })

    if not access_token or not xero_tenant_id:
        logger.error("xero_credentials_incomplete", extra={
            "tenant_id": tenant_id,
            "has_access_token": bool(access_token),
            "has_xero_tenant_id": bool(xero_tenant_id),
        })
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
        logger.info("xero_http_request", extra={
            "tenant_id": tenant_id, "invoice_number": invoice_number,
            "url": f"{XERO_API_BASE}/Invoices",
        })
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
            logger.info("xero_http_response", extra={
                "tenant_id": tenant_id, "invoice_number": invoice_number,
                "status_code": resp.status_code,
            })
            if not resp.is_success:
                logger.error("xero_http_error", extra={
                    "tenant_id": tenant_id, "invoice_number": invoice_number,
                    "status_code": resp.status_code, "response_body": resp.text,
                })
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
