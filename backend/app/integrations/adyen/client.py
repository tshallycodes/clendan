"""
Adyen API client.
Auth: X-API-Key header (api_key — no OAuth required).
Supports test and live environments.
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

MANAGEMENT_TEST_BASE = "https://management-test.adyen.com/v3"
MANAGEMENT_LIVE_BASE = "https://management-live.adyen.com/v3"
DATA_PLATFORM_TEST_BASE = "https://dataplatform-test.adyen.com/v1"

_circuit = CircuitBreaker("adyen")


def _management_base(environment: str) -> str:
    """Returns the correct Adyen Management API base URL for the given environment."""
    return MANAGEMENT_LIVE_BASE if environment == "live" else MANAGEMENT_TEST_BASE


def _api_headers(api_key: str) -> dict:
    """Returns the required Adyen API request headers. Never logs the api_key."""
    return {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }


async def validate_connection(api_key: str, merchant_account: str, environment: str) -> dict:
    """
    Validates Adyen credentials by calling GET /merchants/{merchant_account}.
    Returns merchant info on success. Raises ValueError on invalid credentials or empty response.
    Raises httpx.HTTPStatusError on 401/403. Raises on network failure.
    """
    base = _management_base(environment)

    async def _call() -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base}/merchants/{merchant_account}",
                headers=_api_headers(api_key),
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)

    merchant_id = data.get("id", "")
    if not merchant_id:
        raise ValueError("Adyen returned empty merchant response — connection aborted")

    return {
        "merchant_id": merchant_id,
        "company_name": data.get("companyId", ""),
        "status": data.get("status", ""),
    }


async def fetch_payments(
    api_key: str,
    merchant_account: str,
    environment: str,
    limit: int = 50,
) -> list[dict]:
    """
    Fetches payment methods for the merchant account via GET /merchants/{merchant_account}/paymentMethods.
    Returns a normalised list of {payment_method_type, status, currencies, countries}.
    Uses exponential backoff with jitter on transient failures.
    """
    base = _management_base(environment)

    async def _call() -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base}/merchants/{merchant_account}/paymentMethods",
                params={"pageSize": limit},
                headers=_api_headers(api_key),
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    payment_methods = raw.get("data", [])

    if not isinstance(payment_methods, list):
        raise ValueError("Adyen /paymentMethods response is malformed")

    return [
        {
            "payment_method_type": pm.get("type", ""),
            "status": pm.get("enabled", False),
            "currencies": pm.get("currencies", []),
            "countries": pm.get("countries", []),
        }
        for pm in payment_methods
        if pm.get("type")
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
                    "Adyen call failed (attempt %d/%d), retrying in %.1fs",
                    attempt + 1,
                    MAX_ATTEMPTS,
                    wait,
                )
                await asyncio.sleep(wait)
    raise last_exc
