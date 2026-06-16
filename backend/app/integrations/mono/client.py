import asyncio
import random

import httpx

from app.core.config import get_settings
from app.core.encryption import decrypt, encrypt
from app.core.logging import get_logger
from app.integrations.mono.circuit_breaker import _circuit

logger = get_logger(__name__)

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0
BASE_URL = "https://api.withmono.com"


def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "mono-sec-key": get_settings().mono_secret_key,
    }


async def initiate_connect_session(tenant_id: str, redirect_url: str) -> dict:
    """
    Creates a Mono Connect session.
    Returns { token, mono_url } — frontend should redirect user to mono_url.
    Amounts from Mono are in base currency units (e.g. Naira for NGN); see mono_amount_to_minor.
    """
    s = get_settings()
    payload = {
        "app": s.mono_app_id,
        "customer": {"name": f"Clendan:{tenant_id[:12]}"},
        "meta": {"ref": tenant_id},
        "scope": "auth",
        "redirect_url": redirect_url,
    }

    async def _call():
        async with httpx.AsyncClient() as c:
            r = await c.post(
                f"{BASE_URL}/v2/connect/session/initiate",
                json=payload,
                headers=_headers(),
                timeout=15.0,
            )
            r.raise_for_status()
            return r.json()

    resp = await _circuit.call(_retry, _call)
    inner = resp.get("data", resp)
    mono_url = inner.get("mono_url", "")
    if not mono_url:
        raise ValueError(f"Mono returned empty mono_url. Response keys: {list(resp.keys())}")
    return {"token": inner.get("token", ""), "mono_url": mono_url}


async def exchange_code(code: str) -> str:
    """
    Exchanges a Mono Connect code for an account ID.
    Returns the encrypted account ID string.
    """

    async def _call():
        async with httpx.AsyncClient() as c:
            r = await c.post(
                f"{BASE_URL}/v2/accounts/auth",
                json={"code": code},
                headers=_headers(),
                timeout=15.0,
            )
            r.raise_for_status()
            return r.json()

    resp = await _circuit.call(_retry, _call)
    inner = resp.get("data", resp)
    account_id = inner.get("id", "")
    if not account_id:
        raise ValueError(f"Mono code exchange returned no account ID. Response keys: {list(resp.keys())}")
    return encrypt(account_id)


async def get_account(encrypted_account_id: str) -> dict:
    """
    Fetches account details for a connected Mono account.
    Returns the raw account dict including institution info.
    """
    account_id = decrypt(encrypted_account_id)

    async def _call():
        async with httpx.AsyncClient() as c:
            r = await c.get(
                f"{BASE_URL}/v2/accounts/{account_id}",
                headers=_headers(),
                timeout=15.0,
            )
            r.raise_for_status()
            return r.json()

    resp = await _circuit.call(_retry, _call)
    inner = resp.get("data", resp)
    account = inner.get("account", inner)
    if not account.get("id"):
        raise ValueError(f"Mono get_account returned malformed response. Response keys: {list(resp.keys())}")
    return account


async def get_transactions(encrypted_account_id: str, page: int = 1) -> dict:
    """
    Fetches a page of transactions for a Mono account.
    Returns { data: [...], meta: { total, pages } }.
    Amounts in the Mono response are base currency units (Naira for NGN).
    """
    account_id = decrypt(encrypted_account_id)

    async def _call():
        async with httpx.AsyncClient() as c:
            r = await c.get(
                f"{BASE_URL}/v2/accounts/{account_id}/transactions",
                headers=_headers(),
                params={"paginate": "true", "page": page},
                timeout=30.0,
            )
            r.raise_for_status()
            return r.json()

    resp = await _circuit.call(_retry, _call)
    inner = resp.get("data", resp)
    return {
        "data": inner if isinstance(inner, list) else inner.get("data", []),
        "meta": resp.get("meta", {"total": 0, "pages": 1}),
    }


def mono_amount_to_minor(amount: float, txn_type: str = "debit") -> int:
    """
    Converts Mono base-unit amount to integer minor units (e.g. kobo for NGN).
    Mono amounts are always positive; type indicates direction.
    Convention: debit (money out) = positive, credit (money in) = negative.
    """
    minor = round(abs(amount) * 100)
    return minor if txn_type == "debit" else -minor


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
                    "Mono call failed (attempt %d/%d), retry in %.1fs",
                    attempt + 1,
                    MAX_ATTEMPTS,
                    wait,
                )
                await asyncio.sleep(wait)
    raise last_exc
