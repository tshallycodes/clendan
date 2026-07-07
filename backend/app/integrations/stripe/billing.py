"""Stripe SaaS billing — Checkout, Customer Portal, and subscription retrieval.

This is Clendan's own subscription billing (charging customers for the product),
which is entirely distinct from the Stripe Connect integration in ``client.py``
(which ingests a tenant's own Stripe payment data as a financial source).

All calls use the platform secret key (``stripe_secret_key``) against the standard
Stripe REST API via httpx — consistent with ``client.py``, no extra SDK dependency.
"""
import asyncio
import random

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.stripe.client import STRIPE_API_BASE

logger = get_logger(__name__)

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0

# Plans that can be purchased self-serve. "enterprise" is sales-led; "free" is the default.
SELF_SERVE_PLANS = ("starter", "growth")


def price_id_for_plan(plan: str) -> str | None:
    """Returns the configured Stripe Price ID for a self-serve plan, or None."""
    settings = get_settings()
    mapping = {
        "starter": settings.stripe_price_starter,
        "growth": settings.stripe_price_growth,
    }
    price_id = mapping.get(plan) or ""
    return price_id or None


def plan_for_price(price_id: str) -> str:
    """Reverse lookup: maps a Stripe Price ID back to a Clendan plan key.

    Built only from non-empty configured prices so unset config never collides.
    Falls back to "free" for any unrecognised price.
    """
    settings = get_settings()
    mapping = {
        settings.stripe_price_starter: "starter",
        settings.stripe_price_growth: "growth",
    }
    mapping.pop("", None)
    return mapping.get(price_id, "free")


async def _stripe_request(
    method: str,
    path: str,
    *,
    data: dict | None = None,
    idempotency_key: str | None = None,
) -> dict:
    """Calls the Stripe REST API with retry + exponential backoff and jitter.

    Uses the platform secret key as HTTP basic-auth username. Never logs token or
    response bodies (they may contain customer PII).
    """
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise RuntimeError("stripe_secret_key not configured")

    headers = {}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    last_exc: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            async with httpx.AsyncClient() as http:
                response = await http.request(
                    method,
                    f"{STRIPE_API_BASE}{path}",
                    data=data,
                    headers=headers,
                    auth=(settings.stripe_secret_key, ""),
                    timeout=15.0,
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            # 4xx (except 429) are deterministic — do not retry
            if exc.response.status_code != 429 and 400 <= exc.response.status_code < 500:
                logger.error(
                    "stripe_billing_client_error method=%s path=%s status=%s",
                    method, path, exc.response.status_code,
                )
                raise
            last_exc = exc
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last_exc = exc

        if attempt < MAX_ATTEMPTS - 1:
            wait = BACKOFF_SECONDS * (2 ** attempt) + random.uniform(0, 0.5)
            logger.warning(
                "stripe_billing_retry method=%s path=%s attempt=%d/%d wait=%.1fs",
                method, path, attempt + 1, MAX_ATTEMPTS, wait,
            )
            await asyncio.sleep(wait)

    raise last_exc if last_exc else RuntimeError("Stripe billing request failed")


async def create_customer(*, tenant_id: str, email: str, name: str) -> str:
    """Creates a Stripe customer for a tenant. Returns the customer id.

    tenant_id is stored in customer metadata so webhook events can be traced back.
    """
    data = {"metadata[tenant_id]": tenant_id}
    if email:
        data["email"] = email
    if name:
        data["name"] = name
    result = await _stripe_request(
        "POST", "/customers", data=data, idempotency_key=f"customer:{tenant_id}",
    )
    customer_id = result.get("id", "")
    if not customer_id:
        raise ValueError("Stripe returned no customer id")
    return customer_id


async def create_checkout_session(
    *,
    customer_id: str,
    price_id: str,
    tenant_id: str,
    success_url: str,
    cancel_url: str,
    idempotency_key: str,
) -> str:
    """Creates a subscription Checkout Session. Returns the hosted checkout URL."""
    data = {
        "mode": "subscription",
        "customer": customer_id,
        "client_reference_id": tenant_id,
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "subscription_data[metadata][tenant_id]": tenant_id,
        "metadata[tenant_id]": tenant_id,
        "allow_promotion_codes": "true",
    }
    result = await _stripe_request(
        "POST", "/checkout/sessions", data=data, idempotency_key=idempotency_key,
    )
    url = result.get("url", "")
    if not url:
        raise ValueError("Stripe returned no checkout url")
    return url


async def create_portal_session(*, customer_id: str, return_url: str) -> str:
    """Creates a Customer Portal session. Returns the hosted portal URL."""
    result = await _stripe_request(
        "POST",
        "/billing_portal/sessions",
        data={"customer": customer_id, "return_url": return_url},
    )
    url = result.get("url", "")
    if not url:
        raise ValueError("Stripe returned no portal url")
    return url


async def fetch_subscription(subscription_id: str) -> dict:
    """Retrieves the current state of a subscription. Empty response is a failure."""
    result = await _stripe_request("GET", f"/subscriptions/{subscription_id}")
    if not result or not result.get("id"):
        raise ValueError("Stripe returned empty subscription")
    return result
