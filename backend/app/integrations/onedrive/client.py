"""
Microsoft OneDrive (Graph API) client.
Reuses Azure app registration from Outlook (same client_id/secret), different scope + redirect_uri.
"""
import asyncio
import random
from datetime import datetime, UTC, timedelta
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.encryption import encrypt_credentials
from app.integrations.onedrive.circuit_breaker import _circuit

logger = get_logger(__name__)

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
ONEDRIVE_SCOPES = "Files.ReadWrite offline_access"
TOKEN_TTL_SECONDS = 3600
SUBSCRIPTION_EXPIRY_MINUTES = 4230  # Maximum allowed by Microsoft Graph

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
                    "onedrive_call_failed attempt=%d/%d retry_in=%.1fs",
                    attempt + 1, MAX_ATTEMPTS, wait,
                )
                await asyncio.sleep(wait)
    raise last_exc


def _auth_base_url() -> str:
    settings = get_settings()
    return f"https://login.microsoftonline.com/{settings.microsoft_tenant_id}/oauth2/v2.0"


def build_auth_url(state: str) -> str:
    """Builds Microsoft OAuth authorization URL with OneDrive scopes."""
    settings = get_settings()
    params = {
        "client_id": settings.microsoft_client_id,
        "response_type": "code",
        "redirect_uri": settings.onedrive_redirect_uri,
        "scope": ONEDRIVE_SCOPES,
        "response_mode": "query",
        "state": state,
    }
    return f"{_auth_base_url()}/authorize?{urlencode(params)}"


async def exchange_code(code: str, tenant_id: str) -> str:
    """Exchanges OAuth code for tokens. Returns encrypted credentials string."""
    settings = get_settings()

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{_auth_base_url()}/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.onedrive_redirect_uri,
                    "client_id": settings.microsoft_client_id,
                    "client_secret": settings.microsoft_client_secret,
                    "scope": ONEDRIVE_SCOPES,
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    expiry = (datetime.now(UTC) + timedelta(seconds=TOKEN_TTL_SECONDS)).isoformat()
    return encrypt_credentials(
        {"access_token": data["access_token"], "refresh_token": data.get("refresh_token", ""), "token_expiry_at": expiry},
        tenant_id,
    )


async def refresh_onedrive_token(refresh_token: str) -> dict:
    """Refreshes Microsoft access token. Returns plaintext dict — caller must re-encrypt."""
    settings = get_settings()

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{_auth_base_url()}/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": settings.microsoft_client_id,
                    "client_secret": settings.microsoft_client_secret,
                    "scope": ONEDRIVE_SCOPES,
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


async def list_pdf_files(access_token: str) -> list:
    """Searches OneDrive for PDF files via Graph search API. Returns [{id, name, size, webUrl}]."""
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GRAPH_API_BASE}/me/drive/root/search(q='.pdf')",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    items = data.get("value", [])
    if not isinstance(items, list):
        raise ValueError("OneDrive search returned unexpected format")

    return [
        {
            "id": item["id"],
            "name": item["name"],
            "size": item.get("size", 0),
            "webUrl": item.get("webUrl", ""),
        }
        for item in items
        if item.get("name", "").lower().endswith(".pdf")
    ]


async def download_file(access_token: str, file_id: str) -> bytes:
    """Downloads a OneDrive file by item ID. Returns raw bytes."""
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GRAPH_API_BASE}/me/drive/items/{file_id}/content",
                headers={"Authorization": f"Bearer {access_token}"},
                follow_redirects=True,
                timeout=60.0,
            )
            response.raise_for_status()
            return response.content

    return await _circuit.call(_retry, _call)


async def upload_file(access_token: str, file_bytes: bytes, filename: str) -> dict:
    """Uploads a file to /Clendan/ in OneDrive using simple PUT (files under 4 MB). Returns item dict."""
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{GRAPH_API_BASE}/me/drive/root:/Clendan/{filename}:/content",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/octet-stream",
                },
                content=file_bytes,
                timeout=60.0,
            )
            response.raise_for_status()
            return response.json()

    return await _circuit.call(_retry, _call)


async def create_subscription(access_token: str, notification_url: str, client_state: str) -> dict:
    """Creates a Graph API drive change subscription. Returns subscription dict with id."""
    expiry_dt = (datetime.now(UTC) + timedelta(minutes=SUBSCRIPTION_EXPIRY_MINUTES)).strftime(
        "%Y-%m-%dT%H:%M:%S.0000000Z"
    )

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GRAPH_API_BASE}/subscriptions",
                json={
                    "changeType": "updated",
                    "notificationUrl": notification_url,
                    "resource": "me/drive/root",
                    "expirationDateTime": expiry_dt,
                    "clientState": client_state,
                },
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    if not data or "id" not in data:
        raise ValueError("Graph API returned invalid subscription response — missing id")
    return data


async def delete_subscription(access_token: str, subscription_id: str) -> None:
    """Deletes a Graph API subscription. Ignores 404."""
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{GRAPH_API_BASE}/subscriptions/{subscription_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15.0,
            )
            if response.status_code == 404:
                return
            response.raise_for_status()

    await _circuit.call(_retry, _call)
