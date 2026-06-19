"""Square OAuth, webhook signature verification, and API calls."""
import asyncio
import base64
import hashlib
import hmac
import random
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.quickbooks.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)

SQUARE_AUTH_URL = "https://connect.squareup.com/oauth2/authorize"
SQUARE_TOKEN_URL = "https://connect.squareup.com/oauth2/token"
SQUARE_REVOKE_URL = "https://connect.squareup.com/oauth2/revoke"
SQUARE_API_BASE = "https://connect.squareup.com/v2"

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0

_circuit = CircuitBreaker("square")

_EVENT_MAP: dict[str, str] = {
    # Reconciliation
    "payment.created": "transaction_posted",
    "payment.updated": "transaction_posted",
    "payment.completed": "transaction_posted",
    "invoice.payment_made": "invoice_received",
    "invoice.created": "invoice_created",
    "invoice.updated": "invoice_updated",
    "invoice.canceled": "invoice_canceled",
    # Refunds
    "refund.created": "refund_created",
    "refund.updated": "refund_updated",
    # Disputes
    "dispute.created": "dispute_created",
    "dispute.state.updated": "dispute_state_changed",
    # Payouts
    "payout.sent": "payout_received",
    "payout.failed": "payout_failed",
}


def verify_square_signature(
    body: bytes,
    sig_header: str,
    secret: str,
    notification_url: str,
) -> bool:
    """Verify Square webhook HMAC-SHA256 signature.

    Square signs: HMAC-SHA256(webhook_signature_key, notification_url + body)
    The result is Base64-encoded and compared to x-square-hmacsha256-signature.
    """
    try:
        signed_payload = notification_url.encode() + body
        expected_bytes = hmac.new(
            secret.encode(), signed_payload, hashlib.sha256
        ).digest()
        expected = base64.b64encode(expected_bytes).decode()
        return hmac.compare_digest(expected, sig_header)
    except Exception:
        return False


def parse_square_event_type(event_type: str) -> str | None:
    """Map Square event type to Clendan orchestrator event type."""
    return _EVENT_MAP.get(event_type)


def build_square_auth_url(state: str) -> str:
    """Builds the Square OAuth authorization URL."""
    settings = get_settings()
    params = {
        "client_id": settings.square_client_id,
        "scope": "PAYMENTS_READ INVOICES_READ MERCHANT_PROFILE_READ",
        "session": "false",
        "state": state,
    }
    return f"{SQUARE_AUTH_URL}?{urlencode(params)}"


async def exchange_square_code(code: str) -> dict:
    """Exchanges OAuth authorization code for access_token and merchant_id.

    Returns: {access_token, merchant_id, expires_at, refresh_token, token_type}
    """
    settings = get_settings()

    async def _call() -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                SQUARE_TOKEN_URL,
                json={
                    "client_id": settings.square_client_id,
                    "client_secret": settings.square_client_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.square_redirect_uri,
                },
                headers={"Square-Version": "2024-01-17"},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _retry(_call)
    return {
        "access_token": data.get("access_token", ""),
        "merchant_id": data.get("merchant_id", ""),
        "expires_at": data.get("expires_at"),
        "refresh_token": data.get("refresh_token", ""),
        "token_type": data.get("token_type", "bearer"),
    }


async def revoke_square_token(access_token: str) -> None:
    """Revokes a Square OAuth access token."""
    settings = get_settings()

    async def _call() -> None:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                SQUARE_REVOKE_URL,
                json={
                    "client_id": settings.square_client_id,
                    "access_token": access_token,
                },
                headers={
                    "Authorization": f"Client {settings.square_client_secret}",
                    "Square-Version": "2024-01-17",
                },
                timeout=15.0,
            )
            response.raise_for_status()

    await _retry(_call)


async def get_square_merchant(access_token: str) -> dict:
    """Fetches Square merchant info to verify connection is live."""

    async def _call() -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SQUARE_API_BASE}/merchants/me",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Square-Version": "2024-01-17",
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    merchant = raw.get("merchant", {})
    if not merchant or not merchant.get("id"):
        raise ValueError("Square returned empty merchant — connection aborted")
    return {
        "merchant_id": merchant.get("id", ""),
        "business_name": merchant.get("business_name", ""),
        "country": merchant.get("country", ""),
        "currency": merchant.get("currency", ""),
        "status": merchant.get("status", ""),
    }


async def fetch_square_payments(access_token: str, limit: int = 100) -> list:
    """Fetches recent Square payments for initial sync. Returns normalised list."""

    async def _call() -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SQUARE_API_BASE}/payments",
                params={"limit": limit, "sort_order": "DESC"},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Square-Version": "2024-01-17",
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    payments = raw.get("payments", [])
    return [
        {
            "square_payment_id": p.get("id", ""),
            "amount_minor": (p.get("amount_money") or {}).get("amount", 0),
            "currency": ((p.get("amount_money") or {}).get("currency") or "USD").upper(),
            "status": p.get("status", ""),
            "source_type": p.get("source_type", ""),
            "created_at": p.get("created_at"),
        }
        for p in payments
        if p.get("id")
    ]


async def fetch_square_locations(access_token: str) -> list[dict]:
    """Returns the merchant's active Square locations. Square requires a location_id for invoices."""

    async def _call() -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SQUARE_API_BASE}/locations",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Square-Version": "2024-01-17",
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    return [loc for loc in raw.get("locations", []) if loc.get("status") == "ACTIVE"]


async def fetch_square_invoices(access_token: str, location_id: str, limit: int = 100) -> list:
    """Fetches recent Square invoices for a location. location_id is required by Square's API."""

    async def _call() -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SQUARE_API_BASE}/invoices",
                params={"location_id": location_id, "limit": limit},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Square-Version": "2024-01-17",
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    invoices = raw.get("invoices", [])
    return [
        {
            "square_invoice_id": inv.get("id", ""),
            "amount_minor": (inv.get("payment_requests") or [{}])[0].get("computed_amount_money", {}).get("amount", 0),
            "currency": (
                (inv.get("payment_requests") or [{}])[0]
                .get("computed_amount_money", {})
                .get("currency") or "USD"
            ).upper(),
            "status": inv.get("status", ""),
            "created_at": inv.get("created_at"),
            "due_date": inv.get("due_date"),
        }
        for inv in invoices
        if inv.get("id")
    ]


async def _retry(fn, *args, **kwargs):
    """Exponential backoff with jitter. Raises on final failure."""
    last_exc: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            return await fn(*args, **kwargs)
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.NetworkError) as exc:
            last_exc = exc
            if attempt < MAX_ATTEMPTS - 1:
                wait = BACKOFF_SECONDS * (2 ** attempt) + random.uniform(0, 0.5)
                logger.warning(
                    "Square call failed (attempt %d/%d), retrying in %.1fs",
                    attempt + 1,
                    MAX_ATTEMPTS,
                    wait,
                )
                await asyncio.sleep(wait)
    raise last_exc or RuntimeError("Square: max retries exceeded")
