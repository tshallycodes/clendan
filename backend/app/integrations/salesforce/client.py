"""
Salesforce OAuth 2.0 Web Server Flow + REST API client.
Handles: auth URL, code exchange, token refresh, accounts, contacts,
opportunities, and contracts.
"""
import asyncio
import random
from datetime import datetime, UTC, timedelta
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.encryption import encrypt_credentials
from app.integrations.salesforce.circuit_breaker import _circuit

logger = get_logger(__name__)

SF_AUTH_URL = "https://login.salesforce.com/services/oauth2/authorize"
SF_TOKEN_URL = "https://login.salesforce.com/services/oauth2/token"
SF_SCOPES = "api refresh_token offline_access"
SF_API_VERSION = "v59.0"

# Salesforce tokens don't expire by default; store with 2-hour TTL for safety
ACCESS_TOKEN_TTL_SECONDS = 7200
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
                    "salesforce_call_failed attempt=%d/%d retry_in=%.1fs",
                    attempt + 1, MAX_ATTEMPTS, wait,
                )
                await asyncio.sleep(wait)
    raise last_exc


def _get_redirect_uri() -> str:
    """Returns salesforce_redirect_uri from settings, falling back to the default path."""
    settings = get_settings()
    uri = getattr(settings, "salesforce_redirect_uri", "") or ""
    if not uri:
        uri = f"{settings.backend_base_url.rstrip('/')}/v1/integrations/salesforce/callback"
    return uri


def build_auth_url(state: str) -> str:
    """Builds the Salesforce OAuth authorization URL."""
    settings = get_settings()
    params = {
        "response_type": "code",
        "client_id": settings.salesforce_client_id,
        "redirect_uri": _get_redirect_uri(),
        "scope": SF_SCOPES,
        "state": state,
    }
    return f"{SF_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str, tenant_id: str) -> str:
    """Exchanges code for tokens. Stores instance_url (needed for all API calls). Returns encrypted creds."""
    settings = get_settings()

    async def _call():
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                SF_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.salesforce_client_id,
                    "client_secret": settings.salesforce_client_secret,
                    "redirect_uri": _get_redirect_uri(),
                    "code": code,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    expiry = (datetime.now(UTC) + timedelta(seconds=ACCESS_TOKEN_TTL_SECONDS)).isoformat()
    return encrypt_credentials({
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "instance_url": data["instance_url"],
        "token_expiry_at": expiry,
    }, tenant_id)


async def refresh_sf_token(refresh_token: str) -> dict:
    """Refreshes token. Returns {access_token, instance_url, token_expiry_at} for token_manager to merge."""
    settings = get_settings()

    async def _call():
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                SF_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": settings.salesforce_client_id,
                    "client_secret": settings.salesforce_client_secret,
                    "refresh_token": refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    expiry = (datetime.now(UTC) + timedelta(seconds=ACCESS_TOKEN_TTL_SECONDS)).isoformat()
    return {
        "access_token": data["access_token"],
        "instance_url": data.get("instance_url", ""),
        "token_expiry_at": expiry,
    }


def get_instance_url(creds: dict) -> str:
    """Extracts instance_url from stored credentials. Raises if missing."""
    url = creds.get("instance_url", "")
    if not url:
        raise ValueError("instance_url missing from Salesforce credentials")
    return url.rstrip("/")


async def _soql_query(access_token: str, instance_url: str, query: str) -> list:
    """Executes a SOQL query and returns the records list."""
    url = f"{instance_url}/services/data/{SF_API_VERSION}/query"

    async def _call():
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                params={"q": query},
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    if not raw:
        raise ValueError("Salesforce returned empty query response")
    return raw.get("records", [])


async def get_accounts(access_token: str, instance_url: str) -> list:
    """Fetches up to 200 Salesforce Accounts."""
    return await _soql_query(
        access_token, instance_url,
        "SELECT Id,Name,BillingCountry,Type FROM Account LIMIT 200",
    )


async def get_contacts(access_token: str, instance_url: str) -> list:
    """Fetches up to 200 Salesforce Contacts."""
    return await _soql_query(
        access_token, instance_url,
        "SELECT Id,FirstName,LastName,Email,AccountId FROM Contact LIMIT 200",
    )


async def get_opportunities(access_token: str, instance_url: str) -> list:
    """Fetches up to 200 Salesforce Opportunities."""
    return await _soql_query(
        access_token, instance_url,
        "SELECT Id,Name,Amount,StageName,CloseDate,AccountId FROM Opportunity LIMIT 200",
    )


async def get_contracts(access_token: str, instance_url: str) -> list:
    """Fetches up to 200 Salesforce Contracts."""
    return await _soql_query(
        access_token, instance_url,
        "SELECT Id,ContractNumber,Status,TotalPrice,StartDate FROM Contract LIMIT 200",
    )


async def revoke_token(access_token: str) -> None:
    """Revokes a Salesforce access token."""
    async def _call():
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                "https://login.salesforce.com/services/oauth2/revoke",
                params={"token": access_token},
            )
            response.raise_for_status()

    await _circuit.call(_retry, _call)
