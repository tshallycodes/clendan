"""
FreshBooks API client.
Handles token exchange, refresh, and data fetching for invoices, clients, payments.
"""
import time
from datetime import datetime, UTC

import httpx

from app.core.config import get_settings

_BASE = "https://api.freshbooks.com"
_TOKEN_URL = f"{_BASE}/auth/oauth/token"
_ME_URL = f"{_BASE}/auth/api/v1/users/me"


def _auth_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


async def exchange_code(code: str) -> dict:
    """Exchanges an authorization code for access + refresh tokens. Returns credential dict."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(
            _TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": settings.freshbooks_client_id,
                "client_secret": settings.freshbooks_client_secret,
                "redirect_uri": settings.freshbooks_redirect_uri,
                "code": code,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        tokens = resp.json()

    expires_in = int(tokens.get("expires_in") or 43200)
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", ""),
        "token_expiry_at": datetime.fromtimestamp(time.time() + expires_in, UTC).isoformat(),
    }


async def refresh_token(refresh_token_val: str) -> dict:
    """Refreshes an expired access token. Returns updated credential dict."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(
            _TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": settings.freshbooks_client_id,
                "client_secret": settings.freshbooks_client_secret,
                "redirect_uri": settings.freshbooks_redirect_uri,
                "refresh_token": refresh_token_val,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        tokens = resp.json()

    expires_in = int(tokens.get("expires_in") or 43200)
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", refresh_token_val),
        "token_expiry_at": datetime.fromtimestamp(time.time() + expires_in, UTC).isoformat(),
    }


async def get_me(access_token: str) -> dict:
    """
    Returns the current user's profile including business memberships.
    The account_id on the first active membership is used for subsequent API calls.
    """
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(_ME_URL, headers=_auth_headers(access_token))
        resp.raise_for_status()
        return resp.json().get("response", {})


def extract_account_id(me: dict) -> str:
    """Extracts the first active business account_id from a /users/me response."""
    memberships = me.get("business_memberships", [])
    if not memberships:
        raise ValueError("No business memberships found in FreshBooks profile")
    return memberships[0]["business"]["account_id"]


async def get_invoices(access_token: str, account_id: str, page: int = 1, per_page: int = 100) -> list[dict]:
    url = f"{_BASE}/accounting/account/{account_id}/invoices/invoices"
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.get(
            url,
            params={"page": page, "per_page": per_page},
            headers=_auth_headers(access_token),
        )
        resp.raise_for_status()
        return resp.json().get("response", {}).get("result", {}).get("invoices", [])


async def get_clients(access_token: str, account_id: str, page: int = 1, per_page: int = 100) -> list[dict]:
    url = f"{_BASE}/accounting/account/{account_id}/users/clients"
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.get(
            url,
            params={"page": page, "per_page": per_page},
            headers=_auth_headers(access_token),
        )
        resp.raise_for_status()
        return resp.json().get("response", {}).get("result", {}).get("clients", [])


async def get_payments(access_token: str, account_id: str, page: int = 1, per_page: int = 100) -> list[dict]:
    url = f"{_BASE}/accounting/account/{account_id}/payments/payments"
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.get(
            url,
            params={"page": page, "per_page": per_page},
            headers=_auth_headers(access_token),
        )
        resp.raise_for_status()
        return resp.json().get("response", {}).get("result", {}).get("payments", [])
