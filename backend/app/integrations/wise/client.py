"""
Wise (TransferWise) API client.
Auth: Bearer token (API token — no OAuth required).
Supports sandbox and live environments.
All calls go through the circuit breaker with exponential backoff.
"""
import asyncio
import random

import httpx

from app.core.logging import get_logger
from app.integrations.quickbooks.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0

WISE_SANDBOX_BASE = "https://api.sandbox.transferwise.tech"
WISE_LIVE_BASE = "https://api.wise.com"

PROFILE_TYPE_BUSINESS = "BUSINESS"
TRANSFERS_ENDPOINT = "/v1/transfers"
PROFILES_ENDPOINT = "/v1/profiles"
TRANSFER_STATUS_FILTER = "outgoing_payment_sent"

_circuit = CircuitBreaker("wise")


def _base_url(environment: str) -> str:
    """Returns the correct Wise API base URL for the given environment."""
    return WISE_LIVE_BASE if environment == "live" else WISE_SANDBOX_BASE


def _auth_headers(api_token: str) -> dict:
    """Returns required auth headers for all Wise API calls."""
    return {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }


async def validate_api_token(api_token: str, environment: str) -> list[dict]:
    """
    Validates a Wise API token by calling GET /v1/profiles.
    Returns a normalised list of {id, type, name} profiles on success.
    Raises ValueError if the response is empty (token valid but no profiles).
    Raises httpx.HTTPStatusError (401/403) if the token is invalid.
    """
    base = _base_url(environment)

    async def _call() -> list:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base}{PROFILES_ENDPOINT}",
                headers=_auth_headers(api_token),
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)

    if not isinstance(raw, list):
        raise ValueError("Wise /v1/profiles returned a non-list response")

    if not raw:
        raise ValueError("Wise API token is valid but no profiles found — cannot connect")

    return [
        {
            "id": p.get("id"),
            "type": (p.get("type") or "").upper(),
            "name": (p.get("details") or {}).get("name") or (p.get("details") or {}).get("firstName", ""),
        }
        for p in raw
        if p.get("id") is not None
    ]


async def fetch_transfers(
    api_token: str,
    environment: str,
    profile_id: int,
    limit: int = 50,
) -> list[dict]:
    """
    Fetches sent transfers for a Wise profile.
    Returns a normalised list of transfer records.
    Uses retry with exponential backoff.
    """
    base = _base_url(environment)

    async def _call() -> list:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base}{TRANSFERS_ENDPOINT}",
                params={
                    "profile": profile_id,
                    "limit": limit,
                    "status": TRANSFER_STATUS_FILTER,
                },
                headers=_auth_headers(api_token),
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)

    if not isinstance(raw, list):
        raise ValueError(
            f"Wise /v1/transfers returned a non-list response for profile {profile_id}"
        )

    return [
        {
            "wise_transfer_id": t.get("id"),
            "source_amount": t.get("sourceValue"),
            "source_currency": (t.get("sourceCurrency") or "").upper(),
            "target_amount": t.get("targetValue"),
            "target_currency": (t.get("targetCurrency") or "").upper(),
            "status": t.get("status", ""),
            "created_on": t.get("created"),
        }
        for t in raw
        if t.get("id") is not None
    ]


async def _retry(fn, *args, **kwargs):
    """Exponential backoff with jitter. Raises the last exception on final failure."""
    last_exc: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            return await fn(*args, **kwargs)
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.NetworkError) as exc:
            last_exc = exc
            if attempt < MAX_ATTEMPTS - 1:
                wait = BACKOFF_SECONDS * (2 ** attempt) + random.uniform(0, 0.5)
                logger.warning(
                    "Wise call failed (attempt %d/%d), retrying in %.1fs",
                    attempt + 1,
                    MAX_ATTEMPTS,
                    wait,
                )
                await asyncio.sleep(wait)
    raise last_exc
