"""NetSuite REST Web Services client — OAuth 2.0 Authorization Code flow."""
import asyncio
import random
from datetime import datetime, UTC, timedelta
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.encryption import encrypt_credentials
from app.integrations.netsuite.circuit_breaker import _circuit

logger = get_logger(__name__)

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0
TOKEN_TTL_SECONDS = 3600

_RECORD_BASE = "https://{account_id}.suitetalk.api.netsuite.com/services/rest/record/v1"
_TOKEN_PATH = "https://{account_id}.suitetalk.api.netsuite.com/services/rest/auth/oauth2/v1/token"


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
                    "netsuite_call_failed attempt=%d/%d retry_in=%.1fs",
                    attempt + 1, MAX_ATTEMPTS, wait,
                )
                await asyncio.sleep(wait)
    raise last_exc


def build_auth_url(state: str) -> str:
    """Returns the NetSuite OAuth authorization URL for the configured account."""
    settings = get_settings()
    account_id = getattr(settings, "netsuite_account_id", "")
    params = {
        "response_type": "code",
        "client_id": getattr(settings, "netsuite_client_id", ""),
        "redirect_uri": getattr(settings, "netsuite_redirect_uri", ""),
        "scope": "rest_webservices",
        "state": state,
    }
    base = f"https://{account_id}.app.netsuite.com/app/login/oauth2/authorize.nl"
    return f"{base}?{urlencode(params)}"


async def exchange_code(code: str, tenant_id: str) -> str:
    """Exchanges authorization code for tokens. Returns encrypted credentials string."""
    settings = get_settings()
    account_id = getattr(settings, "netsuite_account_id", "")
    token_url = _TOKEN_PATH.format(account_id=account_id)

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": getattr(settings, "netsuite_redirect_uri", ""),
                },
                auth=(
                    getattr(settings, "netsuite_client_id", ""),
                    getattr(settings, "netsuite_client_secret", ""),
                ),
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    expiry = (datetime.now(UTC) + timedelta(seconds=TOKEN_TTL_SECONDS)).isoformat()
    raw_creds = {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "token_expiry_at": expiry,
        "account_id": account_id,
    }
    return encrypt_credentials(raw_creds, tenant_id)


async def refresh_netsuite_token(refresh_token: str, account_id: str) -> dict:
    """Refreshes access token. Returns plaintext dict — caller re-encrypts."""
    settings = get_settings()

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                _TOKEN_PATH.format(account_id=account_id),
                data={"grant_type": "refresh_token", "refresh_token": refresh_token},
                auth=(
                    getattr(settings, "netsuite_client_id", ""),
                    getattr(settings, "netsuite_client_secret", ""),
                ),
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    expiry = (datetime.now(UTC) + timedelta(seconds=TOKEN_TTL_SECONDS)).isoformat()
    return {"access_token": data["access_token"], "token_expiry_at": expiry}


def _bearer_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}


async def _get_records(access_token: str, account_id: str, record_type: str) -> list:
    url = f"{_RECORD_BASE.format(account_id=account_id)}/{record_type}?limit=200"

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=_bearer_headers(access_token), timeout=20.0)
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    return data.get("items", [])


async def get_invoices(access_token: str, account_id: str) -> list:
    """GET NetSuite invoice records."""
    return await _get_records(access_token, account_id, "invoice")


async def get_vendors(access_token: str, account_id: str) -> list:
    """GET NetSuite vendor records."""
    return await _get_records(access_token, account_id, "vendor")


async def get_purchase_orders(access_token: str, account_id: str) -> list:
    """GET NetSuite purchaseOrder records."""
    return await _get_records(access_token, account_id, "purchaseOrder")
