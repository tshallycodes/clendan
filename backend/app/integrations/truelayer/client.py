import asyncio
import random
from datetime import datetime, UTC, timedelta
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.encryption import encrypt_credentials
from app.integrations.truelayer.circuit_breaker import _circuit

logger = get_logger(__name__)

TL_AUTH_URL = "https://auth.truelayer.com/"
TL_TOKEN_URL = "https://auth.truelayer.com/connect/token"
TL_API_BASE = "https://api.truelayer.com/data/v1/"
TL_SCOPES = "info accounts balance transactions cards offline_access"
TOKEN_TTL_SECONDS = 3540  # 1 hour minus 60s safety margin
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0


def build_auth_url(state: str) -> str:
    """Builds TrueLayer OAuth2 authorisation URL including UK bank provider list."""
    settings = get_settings()
    params = {
        "response_type": "code",
        "client_id": settings.truelayer_client_id,
        "redirect_uri": settings.truelayer_redirect_uri,
        "scope": TL_SCOPES,
        "state": state,
        "providers": "uk-ob-all+uk-oauth-all",
    }
    return f"{TL_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str, tenant_id: str) -> dict:
    """Exchanges OAuth authorisation code for access + refresh tokens.

    Returns encrypted credentials dict. Never logs token values.
    """
    settings = get_settings()

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                TL_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.truelayer_client_id,
                    "client_secret": settings.truelayer_client_secret,
                    "redirect_uri": settings.truelayer_redirect_uri,
                    "code": code,
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _retry(_call)
    token_expiry_at = (datetime.now(UTC) + timedelta(seconds=TOKEN_TTL_SECONDS)).isoformat()

    plaintext_creds = {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "token_expiry_at": token_expiry_at,
    }
    encrypted = encrypt_credentials(plaintext_creds, tenant_id)
    return {"encrypted_credentials": encrypted, "token_expiry_at": token_expiry_at}


async def refresh_truelayer_token(refresh_token: str) -> dict:
    """Refreshes an expired TrueLayer access token using the refresh token.

    Accepts a plaintext refresh token. Returns a dict with new plaintext token values
    and an updated token_expiry_at. Callers are responsible for re-encrypting.
    """
    settings = get_settings()

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                TL_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": settings.truelayer_client_id,
                    "client_secret": settings.truelayer_client_secret,
                    "refresh_token": refresh_token,
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _retry(_call)
    token_expiry_at = (datetime.now(UTC) + timedelta(seconds=TOKEN_TTL_SECONDS)).isoformat()
    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", refresh_token),
        "token_expiry_at": token_expiry_at,
    }


async def get_accounts(access_token: str) -> list:
    """Fetches all accounts for the connected bank. Returns list of account dicts."""

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{TL_API_BASE}accounts",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    results = raw.get("results", [])
    if not isinstance(results, list):
        raise ValueError("TrueLayer /accounts returned unexpected shape — sync aborted")
    return results


async def get_account_balance(access_token: str, account_id: str) -> dict:
    """Fetches the current balance for a single account."""

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{TL_API_BASE}accounts/{account_id}/balance",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    results = raw.get("results", [])
    if not results:
        raise ValueError(f"TrueLayer balance empty for account_id={account_id}")
    return results[0]


async def get_transactions(
    access_token: str,
    account_id: str,
    from_date: str,
    to_date: str,
) -> list:
    """Fetches transactions for an account within the given date range (ISO 8601 dates)."""

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{TL_API_BASE}accounts/{account_id}/transactions",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"from": from_date, "to": to_date},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    results = raw.get("results", [])
    if not isinstance(results, list):
        raise ValueError(f"TrueLayer /transactions returned unexpected shape for account_id={account_id}")
    return results


async def _retry(fn, *args, **kwargs):
    """Exponential backoff with jitter. Raises last exception after MAX_ATTEMPTS."""
    last_exc = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            return await fn(*args, **kwargs)
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.NetworkError) as exc:
            last_exc = exc
            if attempt < MAX_ATTEMPTS - 1:
                wait = BACKOFF_SECONDS * (2 ** attempt) + random.uniform(0, 0.5)
                logger.warning(
                    "TrueLayer call failed (attempt %d/%d), retrying in %.1fs",
                    attempt + 1,
                    MAX_ATTEMPTS,
                    wait,
                )
                await asyncio.sleep(wait)
    raise last_exc
