"""
Xero OAuth 2.0 + PKCE helpers.
Handles: PKCE generation, auth URL construction, code exchange, token refresh.
PKCE is mandatory for Xero (S256 method).
"""
import asyncio
import base64
import hashlib
import random
import secrets
import time
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.encryption import encrypt_credentials, decrypt_credentials
from app.integrations.xero.circuit_breaker import _circuit

logger = get_logger(__name__)

XERO_AUTH_URL = "https://login.xero.com/identity/connect/authorize"
XERO_TOKEN_URL = "https://identity.xero.com/connect/token"
XERO_CONNECTIONS_URL = "https://api.xero.com/connections"
XERO_SCOPES = "openid profile email accounting.transactions accounting.contacts offline_access"

# Access token lifetime: 30 min. Refresh 60s early.
ACCESS_TOKEN_TTL_SECONDS = 1800
ACCESS_TOKEN_EARLY_REFRESH_SECONDS = 60

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0

# In-process PKCE store: state → {verifier, tenant_id, expires_at}
_pkce_store: dict[str, dict] = {}
PKCE_TTL_SECONDS = 600  # 10 minutes


# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------

def _generate_pkce_pair() -> tuple[str, str]:
    """Returns (code_verifier, code_challenge) for S256 method."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def _store_pkce(state: str, verifier: str, tenant_id: str) -> None:
    """Stores PKCE verifier keyed by state with a 10-minute TTL."""
    _pkce_store[state] = {
        "verifier": verifier,
        "tenant_id": tenant_id,
        "expires_at": time.monotonic() + PKCE_TTL_SECONDS,
    }


def _pop_pkce(state: str) -> dict | None:
    """Retrieves and removes PKCE entry. Returns None if missing or expired."""
    entry = _pkce_store.pop(state, None)
    if entry is None:
        return None
    if time.monotonic() > entry["expires_at"]:
        logger.warning("xero_pkce_expired state=%s", state)
        return None
    return entry


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

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
                    "xero_auth_call_failed attempt=%d/%d retry_in=%.1fs",
                    attempt + 1, MAX_ATTEMPTS, wait,
                )
                await asyncio.sleep(wait)
    raise last_exc


# ---------------------------------------------------------------------------
# Public auth functions
# ---------------------------------------------------------------------------

def build_auth_url(state: str, tenant_id: str) -> str:
    """
    Generates Xero OAuth authorization URL with PKCE.
    Stores PKCE verifier keyed by state for later exchange.
    Returns the URL the frontend should redirect the user to.
    """
    verifier, challenge = _generate_pkce_pair()
    _store_pkce(state, verifier, tenant_id)

    settings = get_settings()
    params = {
        "response_type": "code",
        "client_id": settings.xero_client_id,
        "redirect_uri": settings.xero_redirect_uri,
        "scope": XERO_SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{XERO_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str, state: str, tenant_id: str) -> dict:
    """
    Exchanges authorization code + PKCE verifier for access/refresh tokens.
    Returns encrypted credentials dict with token_expiry_at.
    Raises ValueError if PKCE state is missing/expired.
    """
    pkce = _pop_pkce(state)
    if pkce is None:
        raise ValueError("PKCE state not found or expired — cannot exchange code")

    # Tenant must match what was used when building the auth URL
    if pkce["tenant_id"] != tenant_id:
        raise ValueError("Tenant mismatch on PKCE exchange — possible CSRF attempt")

    settings = get_settings()

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                XERO_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.xero_redirect_uri,
                    "client_id": settings.xero_client_id,
                    "code_verifier": pkce["verifier"],
                },
                auth=(settings.xero_client_id, settings.xero_client_secret),
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)

    from datetime import datetime, UTC, timedelta
    expiry = (
        datetime.now(UTC) + timedelta(seconds=ACCESS_TOKEN_TTL_SECONDS - ACCESS_TOKEN_EARLY_REFRESH_SECONDS)
    ).isoformat()

    raw_creds = {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "token_expiry_at": expiry,
        "id_token": data.get("id_token", ""),
    }
    return encrypt_credentials(raw_creds, tenant_id)


async def get_connections(access_token: str) -> list[dict]:
    """
    Calls GET https://api.xero.com/connections to retrieve connected Xero orgs.
    Returns list of connection dicts: [{id, tenantId, tenantName, tenantType, ...}]
    """
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                XERO_CONNECTIONS_URL,
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    return await _circuit.call(_retry, _call)


async def refresh_xero_token(refresh_token: str) -> dict:
    """
    Refreshes Xero access token using the stored refresh token (plaintext).
    Returns dict with: access_token, refresh_token, token_expiry_at (all plaintext — caller encrypts).
    """
    settings = get_settings()

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                XERO_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": settings.xero_client_id,
                },
                auth=(settings.xero_client_id, settings.xero_client_secret),
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)

    from datetime import datetime, UTC, timedelta
    expiry = (
        datetime.now(UTC) + timedelta(seconds=ACCESS_TOKEN_TTL_SECONDS - ACCESS_TOKEN_EARLY_REFRESH_SECONDS)
    ).isoformat()

    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", refresh_token),
        "token_expiry_at": expiry,
    }
