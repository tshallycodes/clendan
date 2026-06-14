"""
Sage Accounting (Business Cloud) API client.
Handles OAuth exchange, refresh, and data fetching for invoices, contacts, and accounts.
"""
import time
from datetime import datetime, UTC

import httpx

from app.core.config import get_settings

_TOKEN_URL = "https://oauth.accounting.sage.com/token"
_API_BASE = "https://api.accounting.sage.com/v3.1"


def _auth_headers(access_token: str) -> dict:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Application-Id": settings.sage_client_id,
        "Content-Type": "application/json",
    }


async def exchange_code(code: str) -> dict:
    """Exchanges authorization code for access + refresh tokens."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(
            _TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": settings.sage_client_id,
                "client_secret": settings.sage_client_secret,
                "redirect_uri": settings.sage_redirect_uri,
                "code": code,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        tokens = resp.json()

    expires_in = int(tokens.get("expires_in") or 3600)
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", ""),
        "token_expiry_at": datetime.fromtimestamp(time.time() + expires_in, UTC).isoformat(),
    }


async def refresh_token(refresh_token_val: str) -> dict:
    """Refreshes an expired access token."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(
            _TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": settings.sage_client_id,
                "client_secret": settings.sage_client_secret,
                "refresh_token": refresh_token_val,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        tokens = resp.json()

    expires_in = int(tokens.get("expires_in") or 3600)
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", refresh_token_val),
        "token_expiry_at": datetime.fromtimestamp(time.time() + expires_in, UTC).isoformat(),
    }


async def get_business(access_token: str) -> dict:
    """Returns the connected Sage business details."""
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(
            f"{_API_BASE}/business",
            headers=_auth_headers(access_token),
        )
        resp.raise_for_status()
        return resp.json()


async def get_sales_invoices(access_token: str, page: int = 1, per_page: int = 100) -> list[dict]:
    """Fetches sales invoices from Sage."""
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.get(
            f"{_API_BASE}/sales_invoices",
            params={"page": page, "items_per_page": per_page},
            headers=_auth_headers(access_token),
        )
        resp.raise_for_status()
        return resp.json().get("$items", [])


async def get_contacts(access_token: str, page: int = 1, per_page: int = 100) -> list[dict]:
    """Fetches contacts from Sage."""
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.get(
            f"{_API_BASE}/contacts",
            params={"page": page, "items_per_page": per_page},
            headers=_auth_headers(access_token),
        )
        resp.raise_for_status()
        return resp.json().get("$items", [])


async def get_purchase_invoices(access_token: str, page: int = 1, per_page: int = 100) -> list[dict]:
    """Fetches purchase invoices from Sage."""
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.get(
            f"{_API_BASE}/purchase_invoices",
            params={"page": page, "items_per_page": per_page},
            headers=_auth_headers(access_token),
        )
        resp.raise_for_status()
        return resp.json().get("$items", [])
