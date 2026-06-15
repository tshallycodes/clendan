"""Stripe webhook signature verification, event parsing, and Connect OAuth."""
import asyncio
import hashlib
import hmac
import random
import time
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.quickbooks.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)

STRIPE_WEBHOOK_TOLERANCE_SECONDS = 300  # 5 minutes


def verify_stripe_signature(payload: bytes, sig_header: str, secret: str) -> bool:
    """Verify Stripe webhook signature (stripe-signature header).

    Stripe format: t=timestamp,v1=signature,v1=signature2,...
    Signed payload: HMAC-SHA256(secret, f"{timestamp}.{payload}")
    """
    try:
        parts = dict(item.split("=", 1) for item in sig_header.split(",") if "=" in item)
        timestamp = int(parts.get("t", "0"))
        signatures = [v for k, v in parts.items() if k == "v1"]

        if abs(time.time() - timestamp) > STRIPE_WEBHOOK_TOLERANCE_SECONDS:
            return False  # Too old — replay attack protection

        signed_payload = f"{timestamp}.{payload.decode()}"
        expected = hmac.new(
            secret.encode(), signed_payload.encode(), hashlib.sha256
        ).hexdigest()
        return any(hmac.compare_digest(expected, sig) for sig in signatures)
    except Exception:
        return False


def parse_stripe_event_type(event_type: str) -> str | None:
    """Map Stripe event type to Clendan orchestrator event type."""
    _MAP: dict[str, str] = {
        # Reconciliation
        "invoice.payment_succeeded": "invoice_received",
        "invoice.finalized": "invoice_received",
        "invoice.payment_failed": "invoice_payment_failed",
        # Transactions
        "charge.succeeded": "transaction_posted",
        "payment_intent.succeeded": "transaction_posted",
        "charge.refunded": "charge_refunded",
        # Disputes
        "charge.dispute.created": "dispute_created",
        "charge.dispute.closed": "dispute_closed",
        # Payouts / cash position
        "payout.paid": "payout_received",
        "payout.failed": "payout_failed",
    }
    return _MAP.get(event_type)


# ---------------------------------------------------------------------------
# Stripe Connect OAuth
# ---------------------------------------------------------------------------

STRIPE_CONNECT_AUTH_URL = "https://connect.stripe.com/oauth/authorize"
STRIPE_CONNECT_TOKEN_URL = "https://connect.stripe.com/oauth/token"
STRIPE_CONNECT_DEAUTH_URL = "https://connect.stripe.com/oauth/deauthorize"
STRIPE_API_BASE = "https://api.stripe.com/v1"

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0

_circuit = CircuitBreaker("stripe")


def build_stripe_auth_url(state: str) -> str:
    """Builds the Stripe Connect OAuth authorization URL."""
    settings = get_settings()
    params = {
        "response_type": "code",
        "client_id": settings.stripe_client_id,
        "scope": "read_only",
        "state": state,
    }
    return f"{STRIPE_CONNECT_AUTH_URL}?{urlencode(params)}"


async def exchange_stripe_code(code: str) -> dict:
    """Exchanges OAuth authorization code for access_token + stripe_user_id.

    Stripe Connect tokens do not expire — no token_expiry_at is stored.
    Returns: {access_token, stripe_user_id, token_type, scope}
    """
    settings = get_settings()

    async def _call() -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                STRIPE_CONNECT_TOKEN_URL,
                data={"grant_type": "authorization_code", "code": code},
                auth=(settings.stripe_secret_key, ""),
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _retry(_call)
    return {
        "access_token": data["access_token"],
        "stripe_user_id": data["stripe_user_id"],
        "token_type": data.get("token_type", "bearer"),
        "scope": data.get("scope", "read_only"),
    }


async def deauthorize_stripe(stripe_user_id: str) -> None:
    """Revokes Stripe Connect authorization for the given stripe_user_id."""
    settings = get_settings()

    async def _call() -> None:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                STRIPE_CONNECT_DEAUTH_URL,
                data={
                    "client_id": settings.stripe_client_id,
                    "stripe_user_id": stripe_user_id,
                },
                auth=(settings.stripe_secret_key, ""),
                timeout=15.0,
            )
            response.raise_for_status()

    await _retry(_call)


async def get_stripe_account(access_token: str) -> dict:
    """Fetches Stripe account info to verify the connected account is live."""

    async def _call() -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{STRIPE_API_BASE}/account",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    if not raw or not raw.get("id"):
        raise ValueError("Stripe returned empty account — connection aborted")
    return {
        "stripe_account_id": raw.get("id", ""),
        "business_name": (raw.get("business_profile") or {}).get("name") or raw.get("display_name", ""),
        "country": raw.get("country", ""),
        "currency": raw.get("default_currency", ""),
        "email": raw.get("email", ""),
    }


async def fetch_recent_charges(access_token: str, limit: int = 100) -> list:
    """Fetches recent charges for initial sync. Returns normalised list with amount_minor."""

    async def _call() -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{STRIPE_API_BASE}/charges",
                params={"limit": limit},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    charges = raw.get("data", [])
    return [
        {
            "stripe_charge_id": c.get("id", ""),
            "amount_minor": c.get("amount", 0),
            "currency": (c.get("currency") or "usd").upper(),
            "status": c.get("status", ""),
            "description": c.get("description") or "",
            "customer": c.get("customer") or "",
            "created": c.get("created"),
        }
        for c in charges
        if c.get("id")
    ]


async def fetch_recent_invoices(access_token: str, limit: int = 100) -> list:
    """Fetches recent invoices for initial sync. Returns normalised list with amount_minor."""

    async def _call() -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{STRIPE_API_BASE}/invoices",
                params={"limit": limit},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    invoices = raw.get("data", [])
    return [
        {
            "stripe_invoice_id": inv.get("id", ""),
            "amount_minor": inv.get("amount_due", 0),
            "currency": (inv.get("currency") or "usd").upper(),
            "status": inv.get("status", ""),
            "customer": inv.get("customer") or "",
            "due_date": inv.get("due_date"),
            "created": inv.get("created"),
        }
        for inv in invoices
        if inv.get("id")
    ]


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
                    "Stripe call failed (attempt %d/%d), retrying in %.1fs",
                    attempt + 1, MAX_ATTEMPTS, wait,
                )
                await asyncio.sleep(wait)
    raise last_exc
