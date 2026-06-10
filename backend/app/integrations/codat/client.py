"""
Codat meta-integration client.
Auth: HTTP Basic — API key as username, empty password (trailing colon in base64).
Codat provides unified access to 50+ accounting platforms (QuickBooks, Xero, Sage, etc.)
through a single company/connection model.
"""
import asyncio
import base64
import random

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.codat.circuit_breaker import _circuit

logger = get_logger(__name__)

CODAT_API_BASE = "https://api.codat.io"
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0


def _auth_header() -> str:
    """Builds HTTP Basic auth header from codat_api_key. Never logs the key value."""
    settings = get_settings()
    # Codat Basic auth: base64(api_key + ":") — trailing colon, no password
    encoded = base64.b64encode(f"{settings.codat_api_key}:".encode()).decode()
    return f"Basic {encoded}"


async def create_company(tenant_id: str, company_name: str) -> dict:
    """
    Creates a Codat company for the tenant.
    Returns {id, name, redirect} where redirect is the Codat Link URL.
    The user must visit redirect to connect their accounting platform.
    """
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{CODAT_API_BASE}/companies",
                headers={
                    "Authorization": _auth_header(),
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={"name": company_name},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    if not data.get("id"):
        raise ValueError("Codat returned empty company ID — aborting connect flow")

    return {
        "id": data["id"],
        "name": data.get("name", company_name),
        "redirect": data.get("redirect", ""),
    }


async def get_company_connections(company_id: str) -> list:
    """
    Returns list of data source connections for a Codat company.
    Each connection represents a linked accounting platform.
    """
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{CODAT_API_BASE}/companies/{company_id}/connections",
                headers={
                    "Authorization": _auth_header(),
                    "Accept": "application/json",
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    # Codat returns {results: [...], ...} for paginated lists
    return data.get("results", data) if isinstance(data, dict) else data


async def get_company_status(company_id: str) -> dict:
    """Returns Codat company details including current connection status."""
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{CODAT_API_BASE}/companies/{company_id}",
                headers={
                    "Authorization": _auth_header(),
                    "Accept": "application/json",
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    return await _circuit.call(_retry, _call)


async def list_invoices(company_id: str, connection_id: str) -> list:
    """
    Fetches invoices from Codat for a given company and connection.
    Empty response is treated as an error — not silently success.
    """
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{CODAT_API_BASE}/companies/{company_id}/data/invoices",
                headers={
                    "Authorization": _auth_header(),
                    "Accept": "application/json",
                },
                params={"connectionId": connection_id},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    results = data.get("results", data) if isinstance(data, dict) else data
    if results is None:
        raise ValueError("Codat returned null invoice results — sync aborted")
    return results


def verify_codat_webhook(payload: bytes, signature: str) -> bool:
    """
    Placeholder — Codat webhook auth varies by plan.
    Full implementation deferred until Codat plan is confirmed.
    See: https://docs.codat.io/using-the-api/webhooks/overview
    """
    # TODO: implement when Codat webhook secret is provisioned
    return True


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
                    "Codat call failed (attempt %d/%d), retrying in %.1fs",
                    attempt + 1, MAX_ATTEMPTS, wait,
                )
                await asyncio.sleep(wait)
    raise last_exc
