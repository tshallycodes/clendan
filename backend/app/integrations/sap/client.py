"""
SAP S/4HANA Cloud client.
Uses OAuth 2.0 Client Credentials (machine-to-machine) — no redirect flow.
All credentials are passed in as parameters; no global settings used for API calls.
"""
import asyncio
import random
from datetime import datetime, UTC, timedelta

import httpx

from app.core.logging import get_logger
from app.integrations.sap.circuit_breaker import _circuit

logger = get_logger(__name__)

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0
TOKEN_TTL_SECONDS = 3600


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

async def _retry(fn, *args, **kwargs):
    """Exponential backoff with jitter. Raises on final failure."""
    last_exc = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            return await fn(*args, **kwargs)
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.NetworkError) as exc:
            last_exc = exc
            if attempt < MAX_ATTEMPTS - 1:
                wait = BACKOFF_SECONDS * (2 ** attempt) + random.uniform(0, 0.5)
                logger.warning(
                    "sap_call_failed attempt=%d/%d retry_in=%.1fs",
                    attempt + 1, MAX_ATTEMPTS, wait,
                )
                await asyncio.sleep(wait)
    raise last_exc


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

async def get_access_token(client_id: str, client_secret: str, token_url: str) -> dict:
    """
    Fetches an OAuth 2.0 access token via client credentials grant.
    Returns plaintext dict: {access_token, token_expiry_at}.
    Always fetches a fresh token — SAP tokens are short-lived.
    """
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                headers={"Accept": "application/json"},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    return {
        "access_token": data["access_token"],
        "token_expiry_at": (
            datetime.now(UTC) + timedelta(seconds=TOKEN_TTL_SECONDS)
        ).isoformat(),
    }


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _bearer_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}


async def get_supplier_invoices(access_token: str, api_base: str) -> list:
    """
    Fetches supplier invoices from SAP S/4HANA Cloud.
    Returns list of invoice dicts (OData results array).
    """
    url = f"{api_base}/API_SUPPLIER_INVOICE_PROCESS_SRV/A_SupplierInvoice?$top=200&$format=json"

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=_bearer_headers(access_token), timeout=20.0)
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    return data.get("d", {}).get("results", [])


async def get_purchase_orders(access_token: str, api_base: str) -> list:
    """
    Fetches purchase orders from SAP S/4HANA Cloud.
    Returns list of purchase order dicts (OData results array).
    """
    url = f"{api_base}/API_PURCHASEORDER_PROCESS_SRV/A_PurchaseOrder?$top=200&$format=json"

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=_bearer_headers(access_token), timeout=20.0)
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    return data.get("d", {}).get("results", [])


async def get_accounts(access_token: str, api_base: str) -> list:
    """
    Fetches bank accounts from SAP S/4HANA Cloud.
    Returns list of account dicts (OData results array).
    """
    url = f"{api_base}/API_BANKACCOUNTINTERNAL_SRV/A_BankAccount?$top=200&$format=json"

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=_bearer_headers(access_token), timeout=20.0)
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    return data.get("d", {}).get("results", [])
