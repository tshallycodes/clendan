"""
Xero API calls — accounts, contacts, connection revocation.
All calls go through the circuit breaker and retry helper.
"""
import asyncio
import random

import httpx

from app.core.logging import get_logger
from app.integrations.xero.circuit_breaker import _circuit

logger = get_logger(__name__)

XERO_API_BASE = "https://api.xero.com/api.xro/2.0"
XERO_CONNECTIONS_URL = "https://api.xero.com/connections"

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0


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
                    "xero_api_call_failed attempt=%d/%d retry_in=%.1fs",
                    attempt + 1, MAX_ATTEMPTS, wait,
                )
                await asyncio.sleep(wait)
    raise last_exc


async def get_accounts(access_token: str, xero_tenant_id: str) -> list:
    """
    GET /api.xro/2.0/Accounts — returns list of chart-of-accounts entries.
    Validates response is non-empty before returning.
    """
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{XERO_API_BASE}/Accounts",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Xero-Tenant-Id": xero_tenant_id,
                    "Accept": "application/json",
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    accounts = raw.get("Accounts", [])
    if not isinstance(accounts, list):
        raise ValueError("Xero returned unexpected Accounts shape — sync aborted")
    return accounts


async def get_contacts(access_token: str, xero_tenant_id: str) -> list:
    """
    GET /api.xro/2.0/Contacts — returns list of contacts (suppliers, customers).
    Validates response is non-empty before returning.
    """
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{XERO_API_BASE}/Contacts",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Xero-Tenant-Id": xero_tenant_id,
                    "Accept": "application/json",
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    contacts = raw.get("Contacts", [])
    if not isinstance(contacts, list):
        raise ValueError("Xero returned unexpected Contacts shape — sync aborted")
    return contacts


async def revoke_connection(access_token: str, connection_id: str) -> None:
    """
    DELETE https://api.xero.com/connections/{connection_id}
    Revokes the specific Xero org connection.
    """
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{XERO_CONNECTIONS_URL}/{connection_id}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
                timeout=10.0,
            )
            response.raise_for_status()

    await _circuit.call(_retry, _call)
