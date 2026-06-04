import asyncio
import random

import httpx

from app.core.config import get_settings
from app.core.encryption import decrypt, encrypt
from app.core.logging import get_logger
from app.integrations.plaid.circuit_breaker import _circuit

logger = get_logger(__name__)

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0


def _base_url() -> str:
    env = get_settings().plaid_env
    return f"https://{env}.plaid.com"


def _headers() -> dict:
    s = get_settings()
    return {
        "Content-Type": "application/json",
        "PLAID-CLIENT-ID": s.plaid_client_id,
        "PLAID-SECRET": s.plaid_secret,
    }


async def create_link_token(user_id: str, tenant_id: str) -> str:
    """Creates a Plaid Link token. Returns the link_token string."""
    payload = {
        "user": {"client_user_id": f"{tenant_id}:{user_id}"},
        "client_name": "Clendan",
        "products": ["transactions"],
        "country_codes": ["US", "GB"],
        "language": "en",
    }

    async def _call():
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{_base_url()}/link/token/create", json=payload, headers=_headers(), timeout=15.0)
            r.raise_for_status()
            return r.json()

    data = await _circuit.call(_retry, _call)
    link_token = data.get("link_token", "")
    if not link_token:
        raise ValueError("Plaid returned empty link_token")
    return link_token


async def exchange_public_token(public_token: str) -> dict:
    """Exchanges a public_token for access_token + item_id. Returns encrypted credentials dict."""

    async def _call():
        async with httpx.AsyncClient() as c:
            r = await c.post(
                f"{_base_url()}/item/public_token/exchange",
                json={"public_token": public_token},
                headers=_headers(),
                timeout=15.0,
            )
            r.raise_for_status()
            return r.json()

    data = await _circuit.call(_retry, _call)
    access_token = data.get("access_token", "")
    item_id = data.get("item_id", "")
    if not access_token or not item_id:
        raise ValueError("Plaid token exchange returned incomplete data")
    return {
        "access_token": encrypt(access_token),
        "item_id": item_id,
    }


async def get_accounts(encrypted_access: str) -> list[dict]:
    """Fetches accounts for an item. Validates before returning."""
    access_token = decrypt(encrypted_access)

    async def _call():
        async with httpx.AsyncClient() as c:
            r = await c.post(
                f"{_base_url()}/accounts/get",
                json={"access_token": access_token},
                headers=_headers(),
                timeout=15.0,
            )
            r.raise_for_status()
            return r.json()

    data = await _circuit.call(_retry, _call)
    accounts = data.get("accounts", [])
    if not isinstance(accounts, list):
        raise ValueError("Plaid accounts response is malformed")
    return accounts


async def sync_transactions(encrypted_access: str, cursor: str | None = None) -> dict:
    """
    Fetches transactions using the cursor-based sync API.
    Returns {"added": [...], "modified": [...], "removed": [...], "next_cursor": str, "has_more": bool}
    """
    access_token = decrypt(encrypted_access)
    body: dict = {"access_token": access_token}
    if cursor:
        body["cursor"] = cursor

    async def _call():
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{_base_url()}/transactions/sync", json=body, headers=_headers(), timeout=30.0)
            r.raise_for_status()
            return r.json()

    data = await _circuit.call(_retry, _call)
    return {
        "added": data.get("added", []),
        "modified": data.get("modified", []),
        "removed": data.get("removed", []),
        "next_cursor": data.get("next_cursor", ""),
        "has_more": data.get("has_more", False),
    }


def plaid_amount_to_minor(amount: float, currency: str = "USD") -> int:
    """
    Converts Plaid float amount to integer minor units (cents/pence).
    Plaid positive = debit (money out), negative = credit (money in).
    """
    return round(amount * 100)


async def _retry(fn, *args, **kwargs):
    last_exc = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            return await fn(*args, **kwargs)
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.NetworkError) as exc:
            last_exc = exc
            if attempt < MAX_ATTEMPTS - 1:
                wait = BACKOFF_SECONDS * (2 ** attempt) + random.uniform(0, 0.5)
                logger.warning(
                    "Plaid call failed (attempt %d/%d), retry in %.1fs",
                    attempt + 1,
                    MAX_ATTEMPTS,
                    wait,
                )
                await asyncio.sleep(wait)
    raise last_exc
