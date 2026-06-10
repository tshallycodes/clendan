"""
GoCardless API client.
Auth: Bearer token (API key — no OAuth required).
Supports sandbox and live environments.
All calls go through the circuit breaker with exponential backoff.
"""
import asyncio
import hashlib
import hmac
import random

import httpx

from app.core.logging import get_logger
from app.integrations.gocardless.circuit_breaker import _circuit

logger = get_logger(__name__)

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0

GC_LIVE_BASE = "https://api.gocardless.com"
GC_SANDBOX_BASE = "https://api-sandbox.gocardless.com"


def get_api_base(environment: str) -> str:
    """Returns the correct GoCardless API base URL for the given environment."""
    return GC_LIVE_BASE if environment == "live" else GC_SANDBOX_BASE


def _headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "GoCardless-Version": "2015-07-06",
        "Content-Type": "application/json",
    }


async def validate_api_key(access_token: str, environment: str) -> dict:
    """
    Validates a GoCardless API key by calling GET /creditors.
    Returns creditor info on success. Raises on invalid key or empty response.
    """
    base = get_api_base(environment)

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base}/creditors",
                headers=_headers(access_token),
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    creditors = data.get("creditors", [])
    if not isinstance(creditors, list):
        raise ValueError("GoCardless /creditors response is malformed")
    return {"creditors": creditors, "environment": environment}


async def get_mandates(access_token: str, environment: str) -> list:
    """Fetches all mandates for the connected GoCardless account."""
    base = get_api_base(environment)

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base}/mandates",
                headers=_headers(access_token),
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    mandates = data.get("mandates", [])
    if not isinstance(mandates, list):
        raise ValueError("GoCardless /mandates response is malformed")
    return mandates


async def get_payments(access_token: str, environment: str) -> list:
    """Fetches all payments for the connected GoCardless account."""
    base = get_api_base(environment)

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base}/payments",
                headers=_headers(access_token),
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    payments = data.get("payments", [])
    if not isinstance(payments, list):
        raise ValueError("GoCardless /payments response is malformed")
    return payments


async def get_payouts(access_token: str, environment: str) -> list:
    """Fetches all payouts for the connected GoCardless account."""
    base = get_api_base(environment)

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base}/payouts",
                headers=_headers(access_token),
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    payouts = data.get("payouts", [])
    if not isinstance(payouts, list):
        raise ValueError("GoCardless /payouts response is malformed")
    return payouts


def verify_gocardless_webhook(payload: bytes, signature: str, webhook_secret: str) -> bool:
    """
    Verifies a GoCardless webhook payload using HMAC-SHA256.
    Returns True if the signature matches, False otherwise.
    """
    expected = hmac.new(
        webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def _retry(fn, *args, **kwargs):
    """Exponential backoff with jitter. Raises the last exception on final failure."""
    last_exc = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            return await fn(*args, **kwargs)
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.NetworkError) as exc:
            last_exc = exc
            if attempt < MAX_ATTEMPTS - 1:
                wait = BACKOFF_SECONDS * (2 ** attempt) + random.uniform(0, 0.5)
                logger.warning(
                    "GoCardless call failed (attempt %d/%d), retrying in %.1fs",
                    attempt + 1,
                    MAX_ATTEMPTS,
                    wait,
                )
                await asyncio.sleep(wait)
    raise last_exc
