"""PayPal OAuth, webhook verification, and API calls."""
import asyncio
import random
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.quickbooks.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0

_circuit = CircuitBreaker("paypal")

_EVENT_MAP: dict[str, str] = {
    "PAYMENT.CAPTURE.COMPLETED": "transaction_posted",
    "INVOICING.INVOICE.PAID": "invoice_received",
}


def _api_base(settings) -> str:
    """Returns the correct PayPal API base URL based on environment setting."""
    if settings.paypal_env == "sandbox":
        return "https://api-m.sandbox.paypal.com"
    return "https://api-m.paypal.com"


async def get_paypal_app_token(settings) -> str:
    """Obtains a PayPal app-level access token via client credentials flow."""

    async def _call() -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{_api_base(settings)}/v1/oauth2/token",
                data={"grant_type": "client_credentials"},
                auth=(settings.paypal_client_id, settings.paypal_client_secret),
                headers={"Accept": "application/json"},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _retry(_call)
    token = data.get("access_token", "")
    if not token:
        raise ValueError("PayPal returned empty app token")
    return token


async def verify_paypal_webhook(
    headers: dict,
    body: bytes,
    webhook_id: str,
    settings,
) -> bool:
    """Verifies a PayPal webhook using the PayPal verify-webhook-signature API.

    Returns True only if PayPal confirms verification_status == SUCCESS.
    All required header fields must be present.
    """
    required = [
        "paypal-auth-algo",
        "paypal-cert-url",
        "paypal-transmission-id",
        "paypal-transmission-sig",
        "paypal-transmission-time",
    ]
    for key in required:
        if not headers.get(key):
            logger.warning("PayPal webhook missing header: %s", key)
            return False

    try:
        import json
        app_token = await get_paypal_app_token(settings)

        async def _call() -> dict:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{_api_base(settings)}/v1/notifications/verify-webhook-signature",
                    json={
                        "auth_algo": headers["paypal-auth-algo"],
                        "cert_url": headers["paypal-cert-url"],
                        "transmission_id": headers["paypal-transmission-id"],
                        "transmission_sig": headers["paypal-transmission-sig"],
                        "transmission_time": headers["paypal-transmission-time"],
                        "webhook_id": webhook_id,
                        "webhook_event": json.loads(body),
                    },
                    headers={"Authorization": f"Bearer {app_token}"},
                    timeout=15.0,
                )
                response.raise_for_status()
                return response.json()

        result = await _retry(_call)
        return result.get("verification_status") == "SUCCESS"
    except Exception as exc:
        logger.warning("PayPal webhook verification failed: %s", type(exc).__name__)
        return False


def parse_paypal_event_type(event_type: str) -> str | None:
    """Map PayPal event type to Clendan orchestrator event type."""
    return _EVENT_MAP.get(event_type)


def build_paypal_auth_url(state: str) -> str:
    """Builds the PayPal Connect OAuth authorization URL for merchant onboarding."""
    settings = get_settings()
    scope = (
        "openid profile email address "
        "https://uri.paypal.com/services/invoicing "
        "https://uri.paypal.com/services/payments/realtimepayment"
    )
    params = {
        "flowEntry": "static",
        "client_id": settings.paypal_client_id,
        "scope": scope,
        "redirect_uri": settings.paypal_redirect_uri,
        "state": state,
    }
    return f"https://www.paypal.com/connect?{urlencode(params)}"


async def exchange_paypal_code(code: str) -> dict:
    """Exchanges OAuth authorization code for access_token and refresh_token.

    Returns: {access_token, refresh_token, token_type, expires_in, scope}
    """
    settings = get_settings()

    async def _call() -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{_api_base(settings)}/v1/oauth2/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.paypal_redirect_uri,
                },
                auth=(settings.paypal_client_id, settings.paypal_client_secret),
                headers={"Accept": "application/json"},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _retry(_call)
    return {
        "access_token": data.get("access_token", ""),
        "refresh_token": data.get("refresh_token", ""),
        "token_type": data.get("token_type", "Bearer"),
        "expires_in": data.get("expires_in", 3600),
        "scope": data.get("scope", ""),
    }


async def revoke_paypal_token(access_token: str) -> None:
    """Revokes a PayPal OAuth access token."""
    settings = get_settings()

    async def _call() -> None:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{_api_base(settings)}/v1/oauth2/token/revoke",
                data={"token": access_token},
                auth=(settings.paypal_client_id, settings.paypal_client_secret),
                timeout=15.0,
            )
            response.raise_for_status()

    await _retry(_call)


async def get_paypal_merchant_info(access_token: str) -> dict:
    """Fetches PayPal user/merchant info to verify connection is live."""
    settings = get_settings()

    async def _call() -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{_api_base(settings)}/v1/identity/openidconnect/userinfo",
                params={"schema": "openid"},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    if not raw or not raw.get("user_id"):
        raise ValueError("PayPal returned empty user info — connection aborted")
    return {
        "user_id": raw.get("user_id", ""),
        "email": raw.get("email", ""),
        "name": raw.get("name", ""),
        "verified_account": raw.get("verified_account", False),
    }


async def fetch_paypal_transactions(access_token: str) -> list:
    """Fetches recent PayPal payment captures for initial sync."""
    settings = get_settings()

    async def _call() -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{_api_base(settings)}/v2/payments/captures",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    try:
        raw = await _circuit.call(_retry, _call)
    except Exception:
        # PayPal captures endpoint may require a specific ID — return empty on generic fetch
        logger.warning("PayPal transactions fetch returned empty or unsupported — skipping initial sync")
        return []

    transactions = raw.get("captures", [])
    return [
        {
            "paypal_capture_id": t.get("id", ""),
            "amount_minor": int(float((t.get("amount") or {}).get("value", "0")) * 100),
            "currency": ((t.get("amount") or {}).get("currency_code") or "USD").upper(),
            "status": t.get("status", ""),
            "create_time": t.get("create_time"),
        }
        for t in transactions
        if t.get("id")
    ]


async def fetch_paypal_invoices(access_token: str) -> list:
    """Fetches recent PayPal invoices for initial sync."""
    settings = get_settings()

    async def _call() -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{_api_base(settings)}/v2/invoicing/invoices",
                params={"total_count_required": "true", "page_size": 100},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    items = raw.get("items", [])
    return [
        {
            "paypal_invoice_id": inv.get("id", ""),
            "amount_minor": int(
                float(
                    (inv.get("amount") or {}).get("value", "0")
                ) * 100
            ),
            "currency": ((inv.get("amount") or {}).get("currency_code") or "USD").upper(),
            "status": inv.get("status", ""),
            "create_time": inv.get("detail", {}).get("invoice_date"),
            "due_date": inv.get("detail", {}).get("payment_term", {}).get("due_date"),
        }
        for inv in items
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
                    "PayPal call failed (attempt %d/%d), retrying in %.1fs",
                    attempt + 1,
                    MAX_ATTEMPTS,
                    wait,
                )
                await asyncio.sleep(wait)
    raise last_exc
