"""
HubSpot OAuth 2.0 client.
Handles: auth URL construction, code exchange, token refresh, portal info,
contacts, companies, and deals.
"""
import asyncio
import random
from datetime import datetime, UTC, timedelta
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.encryption import encrypt_credentials
from app.integrations.hubspot.circuit_breaker import _circuit

logger = get_logger(__name__)

HS_AUTH_URL = "https://app.hubspot.com/oauth/authorize"
HS_TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"
HS_API_BASE = "https://api.hubapi.com"
HS_SCOPES = "crm.objects.contacts.read crm.objects.deals.read crm.objects.companies.read"

ACCESS_TOKEN_TTL_SECONDS = 1800  # HubSpot access tokens expire in 30 minutes

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0


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
                    "hubspot_call_failed attempt=%d/%d retry_in=%.1fs",
                    attempt + 1, MAX_ATTEMPTS, wait,
                )
                await asyncio.sleep(wait)
    raise last_exc


# ---------------------------------------------------------------------------
# OAuth helpers
# ---------------------------------------------------------------------------

def build_auth_url(state: str) -> str:
    """Builds the HubSpot OAuth authorization URL."""
    settings = get_settings()
    params = {
        "client_id": settings.hubspot_client_id,
        "redirect_uri": settings.hubspot_redirect_uri,
        "scope": HS_SCOPES,
        "state": state,
    }
    return f"{HS_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str, tenant_id: str) -> dict:
    """
    Exchanges authorization code for access + refresh tokens.
    Returns encrypted credentials dict with token_expiry_at.
    """
    settings = get_settings()

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                HS_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.hubspot_client_id,
                    "client_secret": settings.hubspot_client_secret,
                    "redirect_uri": settings.hubspot_redirect_uri,
                    "code": code,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)

    expiry = (datetime.now(UTC) + timedelta(seconds=ACCESS_TOKEN_TTL_SECONDS)).isoformat()

    raw_creds = {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "token_expiry_at": expiry,
    }
    return encrypt_credentials(raw_creds, tenant_id)


async def refresh_hubspot_token(refresh_token: str) -> dict:
    """
    Refreshes HubSpot access token using the stored refresh token (plaintext).
    Returns dict with: access_token, refresh_token, expires_in, token_expiry_at.
    Caller (token_manager) merges this into stored creds and re-encrypts.
    """
    settings = get_settings()

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                HS_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": settings.hubspot_client_id,
                    "client_secret": settings.hubspot_client_secret,
                    "refresh_token": refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)

    expires_in = data.get("expires_in", ACCESS_TOKEN_TTL_SECONDS)
    expiry = (datetime.now(UTC) + timedelta(seconds=expires_in)).isoformat()

    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", refresh_token),
        "expires_in": expires_in,
        "token_expiry_at": expiry,
    }


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

async def get_portal_info(access_token: str) -> dict:
    """
    Fetches HubSpot portal/account info via GET /oauth/v1/access-tokens/{token}.
    Returns raw response dict containing hub_id (portal_id), hub_domain, etc.
    """
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{HS_API_BASE}/oauth/v1/access-tokens/{access_token}",
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    if not raw:
        raise ValueError("HubSpot returned empty portal info — aborting")
    return raw


async def get_contacts(access_token: str, after: str | None = None) -> dict:
    """
    Fetches one page of CRM contacts via GET /crm/v3/objects/contacts.
    Pass `after` cursor for subsequent pages.
    Returns raw HubSpot paged response dict.
    """
    params: dict = {"limit": 100, "properties": "firstname,lastname,email,company,phone"}
    if after:
        params["after"] = after

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{HS_API_BASE}/crm/v3/objects/contacts",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    if not raw:
        raise ValueError("HubSpot returned empty contacts response")
    return raw


async def get_companies(access_token: str, after: str | None = None) -> dict:
    """
    Fetches one page of CRM companies via GET /crm/v3/objects/companies.
    Pass `after` cursor for subsequent pages.
    Returns raw HubSpot paged response dict.
    """
    params: dict = {"limit": 100, "properties": "name,domain,industry,city,country"}
    if after:
        params["after"] = after

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{HS_API_BASE}/crm/v3/objects/companies",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    if not raw:
        raise ValueError("HubSpot returned empty companies response")
    return raw


async def get_deals(access_token: str, after: str | None = None) -> dict:
    """
    Fetches one page of CRM deals via GET /crm/v3/objects/deals.
    Pass `after` cursor for subsequent pages.
    Returns raw HubSpot paged response dict.
    """
    params: dict = {"limit": 100, "properties": "dealname,amount,dealstage,closedate,pipeline"}
    if after:
        params["after"] = after

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{HS_API_BASE}/crm/v3/objects/deals",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    if not raw:
        raise ValueError("HubSpot returned empty deals response")
    return raw
