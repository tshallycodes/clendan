"""
Microsoft Dynamics 365 client.
Handles OAuth 2.0 via the Microsoft identity platform and Dynamics Web API calls.
Each customer has their own Dynamics org URL and Azure tenant.
"""
import asyncio
import random
from datetime import datetime, UTC, timedelta
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.dynamics.circuit_breaker import _circuit
from app.integrations.encryption import encrypt_credentials

logger = get_logger(__name__)

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
TOKEN_TTL_SECONDS = 3600
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0



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
                    "dynamics_call_failed attempt=%d/%d retry_in=%.1fs",
                    attempt + 1, MAX_ATTEMPTS, wait,
                )
                await asyncio.sleep(wait)
    raise last_exc



def _auth_base_url(tenant_id: str) -> str:
    """Returns Microsoft identity platform base URL for the given Azure tenant_id."""
    return f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0"


def build_auth_url(state: str, dynamics_org_url: str = "") -> str:
    """
    Builds Microsoft OAuth authorization URL for Dynamics 365.
    dynamics_org_url is the customer-specific Dynamics org URL.
    """
    settings = get_settings()
    redirect_uri = getattr(settings, "dynamics_redirect_uri", "http://localhost:8000/v1/integrations/dynamics/callback")

    if dynamics_org_url:
        scope = f"{dynamics_org_url}/.default offline_access"
    else:
        scope = "Dynamics CRM user_impersonation offline_access"

    params = {
        "client_id": settings.microsoft_client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": scope,
        "response_mode": "query",
        "state": state,
    }
    return f"{_auth_base_url(settings.microsoft_tenant_id)}/authorize?{urlencode(params)}"


async def exchange_code(code: str, tenant_id: str, dynamics_org_url: str = "") -> str:
    """
    Exchanges OAuth authorization code for access + refresh tokens.
    tenant_id is the Clendan internal tenant ID — used to derive the encryption key.
    Returns encrypted credentials string.
    """
    settings = get_settings()
    redirect_uri = getattr(settings, "dynamics_redirect_uri", "http://localhost:8000/v1/integrations/dynamics/callback")

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{_auth_base_url(settings.microsoft_tenant_id)}/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": settings.microsoft_client_id,
                    "client_secret": settings.microsoft_client_secret,
                },
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
        "dynamics_org_url": dynamics_org_url,
    }
    return encrypt_credentials(raw_creds, tenant_id)


async def refresh_dynamics_token(refresh_token: str) -> dict:
    """
    Refreshes Microsoft access token using the stored refresh token (plaintext).
    Returns dict with access_token, refresh_token, token_expiry_at (all plaintext).
    Caller is responsible for re-encrypting before storage.
    """
    settings = get_settings()

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{_auth_base_url(settings.microsoft_tenant_id)}/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": settings.microsoft_client_id,
                    "client_secret": settings.microsoft_client_secret,
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)

    expiry = (datetime.now(UTC) + timedelta(seconds=TOKEN_TTL_SECONDS)).isoformat()
    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", refresh_token),
        "token_expiry_at": expiry,
    }



def _dynamics_headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
        "Accept": "application/json",
    }


async def get_invoices(access_token: str, org_url: str) -> list:
    """GET invoices from Dynamics 365 Web API. Returns list of invoice dicts."""
    url = (
        f"{org_url}/api/data/v9.2/invoices"
        "?$select=invoiceid,name,totalamount,invoicenumber,customerid,createdon&$top=200"
    )

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=_dynamics_headers(access_token), timeout=20.0)
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    return data.get("value", [])


async def get_accounts(access_token: str, org_url: str) -> list:
    """GET accounts from Dynamics 365 Web API. Returns list of account dicts."""
    url = (
        f"{org_url}/api/data/v9.2/accounts"
        "?$select=accountid,name,emailaddress1,telephone1&$top=200"
    )

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=_dynamics_headers(access_token), timeout=20.0)
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    return data.get("value", [])


async def get_opportunities(access_token: str, org_url: str) -> list:
    """GET opportunities from Dynamics 365 Web API. Returns list of opportunity dicts."""
    url = (
        f"{org_url}/api/data/v9.2/opportunities"
        "?$select=opportunityid,name,estimatedvalue,statecode&$top=200"
    )

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=_dynamics_headers(access_token), timeout=20.0)
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    return data.get("value", [])
