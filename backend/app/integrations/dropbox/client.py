"""
Dropbox OAuth 2.0 client.
Handles auth URL construction, token exchange/refresh, file listing, download, and revocation.
"""
import asyncio
import random
from datetime import datetime, UTC, timedelta
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.encryption import encrypt_credentials
from app.integrations.dropbox.circuit_breaker import _circuit

logger = get_logger(__name__)

DB_AUTH_URL = "https://www.dropbox.com/oauth2/authorize"
DB_TOKEN_URL = "https://api.dropboxapi.com/oauth2/token"
DB_API_BASE = "https://api.dropboxapi.com/2"
DB_CONTENT_BASE = "https://content.dropboxapi.com/2"

TOKEN_TTL_SECONDS = 14400  # Dropbox short-lived tokens: 4 hours
TOKEN_EARLY_REFRESH_SECONDS = 120
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
                    "dropbox_call_failed attempt=%d/%d retry_in=%.1fs",
                    attempt + 1, MAX_ATTEMPTS, wait,
                )
                await asyncio.sleep(wait)
    raise last_exc


def build_auth_url(state: str) -> str:
    """Builds Dropbox OAuth authorization URL with offline (refresh token) access."""
    settings = get_settings()
    params = {
        "response_type": "code",
        "client_id": settings.dropbox_client_id,
        "redirect_uri": settings.dropbox_redirect_uri,
        "state": state,
        "token_access_type": "offline",
    }
    return f"{DB_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str, tenant_id: str) -> str:
    """Exchanges OAuth code for tokens. Returns encrypted credentials string."""
    settings = get_settings()

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                DB_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.dropbox_redirect_uri,
                    "client_id": settings.dropbox_client_id,
                    "client_secret": settings.dropbox_client_secret,
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)

    expiry = (
        datetime.now(UTC) + timedelta(seconds=TOKEN_TTL_SECONDS - TOKEN_EARLY_REFRESH_SECONDS)
    ).isoformat()

    raw_creds = {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "token_expiry_at": expiry,
    }
    return encrypt_credentials(raw_creds, tenant_id)


async def refresh_dropbox_token(refresh_token: str) -> dict:
    """Refreshes Dropbox access token. Returns plaintext dict — caller must re-encrypt."""
    settings = get_settings()

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                DB_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": settings.dropbox_client_id,
                    "client_secret": settings.dropbox_client_secret,
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)

    expiry = (
        datetime.now(UTC) + timedelta(seconds=TOKEN_TTL_SECONDS - TOKEN_EARLY_REFRESH_SECONDS)
    ).isoformat()

    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", refresh_token),
        "token_expiry_at": expiry,
    }


async def list_pdf_files(access_token: str) -> list:
    """Lists all PDF files in the connected Dropbox (recursive). Returns [{id, name, path_lower, size}]."""
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{DB_API_BASE}/files/list_folder",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={"path": "", "recursive": True},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    entries = data.get("entries", [])
    if not isinstance(entries, list):
        raise ValueError("Dropbox list_folder returned unexpected format")

    return [
        {
            "id": entry["id"],
            "name": entry["name"],
            "path_lower": entry.get("path_lower", ""),
            "size": entry.get("size", 0),
        }
        for entry in entries
        if entry.get(".tag") == "file" and entry.get("name", "").lower().endswith(".pdf")
    ]


async def download_file(access_token: str, path: str) -> bytes:
    """Downloads a Dropbox file by path_lower. Returns raw bytes."""
    import json as _json

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{DB_CONTENT_BASE}/files/download",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Dropbox-API-Arg": _json.dumps({"path": path}),
                },
                timeout=60.0,
            )
            response.raise_for_status()
            return response.content

    return await _circuit.call(_retry, _call)


async def upload_file(access_token: str, pdf_bytes: bytes, filename: str) -> dict:
    """Upload a PDF to Dropbox under /Clendan/{filename} (autorenames on conflict). Returns file metadata."""
    import json as _json

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{DB_CONTENT_BASE}/files/upload",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/octet-stream",
                    "Dropbox-API-Arg": _json.dumps({
                        "path": f"/Clendan/{filename}",
                        "mode": "add",
                        "autorename": True,
                    }),
                },
                content=pdf_bytes,
                timeout=120.0,
            )
            response.raise_for_status()
            return response.json()

    return await _circuit.call(_retry, _call)


async def revoke_token(access_token: str) -> None:
    """Revokes a Dropbox access token."""
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{DB_API_BASE}/auth/token/revoke",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )
            response.raise_for_status()

    await _retry(_call)
