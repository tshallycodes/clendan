import asyncio
import random
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.encryption import decrypt, encrypt
from app.core.logging import get_logger
from app.integrations.quickbooks.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)

QB_AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
QB_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
QB_REVOKE_URL = "https://developer.api.intuit.com/v2/oauth2/tokens/revoke"
QB_API_BASE = "https://quickbooks.api.intuit.com/v3/company"
QB_SANDBOX_API_BASE = "https://sandbox-quickbooks.api.intuit.com/v3/company"
QB_SCOPES = "com.intuit.quickbooks.accounting"
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0

_circuit = CircuitBreaker("quickbooks")


def get_api_base(sandbox: bool = True) -> str:
    return QB_SANDBOX_API_BASE if sandbox else QB_API_BASE


def build_auth_url(state: str) -> str:
    settings = get_settings()
    params = {
        "client_id": settings.quickbooks_client_id,
        "response_type": "code",
        "scope": QB_SCOPES,
        "redirect_uri": settings.quickbooks_redirect_uri,
        "state": state,
    }
    return f"{QB_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str, realm_id: str) -> dict:
    """Exchanges OAuth authorization code for access + refresh tokens."""
    settings = get_settings()

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                QB_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.quickbooks_redirect_uri,
                },
                auth=(settings.quickbooks_client_id, settings.quickbooks_client_secret),
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _retry(_call)
    return {
        "access_token": encrypt(data["access_token"]),
        "refresh_token": encrypt(data["refresh_token"]),
        "realm_id": realm_id,
        "expires_in": data.get("expires_in", 3600),
        "x_refresh_token_expires_in": data.get("x_refresh_token_expires_in", 8726400),
        "token_type": data.get("token_type", "bearer"),
    }


async def refresh_token(encrypted_refresh: str) -> dict:
    """Refreshes access token using the stored refresh token."""
    settings = get_settings()
    refresh = decrypt(encrypted_refresh)

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                QB_TOKEN_URL,
                data={"grant_type": "refresh_token", "refresh_token": refresh},
                auth=(settings.quickbooks_client_id, settings.quickbooks_client_secret),
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _retry(_call)
    return {
        "access_token": encrypt(data["access_token"]),
        "refresh_token": encrypt(data.get("refresh_token", encrypted_refresh)),
        "expires_in": data.get("expires_in", 3600),
    }


async def get_company_info(encrypted_access: str, realm_id: str, sandbox: bool = True) -> dict:
    """Fetches QuickBooks company info. Validates response before returning."""
    access_token = decrypt(encrypted_access)

    async def _call():
        url = f"{get_api_base(sandbox)}/{realm_id}/companyinfo/{realm_id}"
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    raw = await _circuit.call(_retry, _call)
    company = raw.get("CompanyInfo")
    if not company:
        raise ValueError("QuickBooks returned empty CompanyInfo — sync aborted")
    return {
        "company_name": company.get("CompanyName", ""),
        "legal_name": company.get("LegalName", ""),
        "country": company.get("Country", ""),
        "fiscal_year_start": company.get("FiscalYearStartMonth", ""),
    }


async def revoke_token(encrypted_token: str) -> None:
    """Revokes a QuickBooks token."""
    settings = get_settings()
    token = decrypt(encrypted_token)

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                QB_REVOKE_URL,
                data={"token": token},
                auth=(settings.quickbooks_client_id, settings.quickbooks_client_secret),
                timeout=10.0,
            )
            response.raise_for_status()

    await _retry(_call)


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
                    "QB call failed (attempt %d/%d), retrying in %.1fs",
                    attempt + 1, MAX_ATTEMPTS, wait,
                )
                await asyncio.sleep(wait)
    raise last_exc
