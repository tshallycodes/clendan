"""
Google OAuth 2.0 client — shared by Gmail and Google Drive integrations.
Both use the same OAuth client ID/secret but with different scopes and redirect URIs.
Token expiry: 1 hour (3600 seconds). Refresh tokens are long-lived.
"""
import asyncio
import random
from datetime import datetime, UTC, timedelta
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.encryption import encrypt_credentials
from app.integrations.google.circuit_breaker import _circuit

logger = get_logger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.readonly"

TOKEN_TTL_SECONDS = 3600
TOKEN_EARLY_REFRESH_SECONDS = 60

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
                    "google_call_failed attempt=%d/%d retry_in=%.1fs",
                    attempt + 1, MAX_ATTEMPTS, wait,
                )
                await asyncio.sleep(wait)
    raise last_exc


# ---------------------------------------------------------------------------
# Auth URL builders
# ---------------------------------------------------------------------------

def build_gmail_auth_url(state: str) -> str:
    """Builds Gmail OAuth authorization URL with offline access."""
    settings = get_settings()
    params = {
        "client_id": settings.google_client_id,
        "response_type": "code",
        "scope": GMAIL_SCOPE,
        "redirect_uri": settings.google_redirect_uri_gmail,
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def build_drive_auth_url(state: str) -> str:
    """Builds Google Drive OAuth authorization URL with offline access."""
    settings = get_settings()
    params = {
        "client_id": settings.google_client_id,
        "response_type": "code",
        "scope": DRIVE_SCOPE,
        "redirect_uri": settings.google_redirect_uri_drive,
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


# ---------------------------------------------------------------------------
# Token operations
# ---------------------------------------------------------------------------

async def exchange_code(code: str, redirect_uri: str, tenant_id: str) -> dict:
    """
    Exchanges OAuth authorization code for access + refresh tokens.
    Returns encrypted credentials dict including token_expiry_at.
    """
    settings = get_settings()

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
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
        "token_type": data.get("token_type", "Bearer"),
    }
    return encrypt_credentials(raw_creds, tenant_id)


async def refresh_google_token(refresh_token: str) -> dict:
    """
    Refreshes Google access token using the stored refresh token (plaintext).
    Returns dict with: access_token, refresh_token, token_expiry_at (all plaintext — caller encrypts).
    """
    settings = get_settings()

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
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


async def get_user_info(access_token: str) -> dict:
    """Fetches Google user info to identify the connected account."""
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()

    return await _circuit.call(_retry, _call)


async def revoke_google_token(token: str) -> None:
    """Revokes a Google OAuth token (access or refresh)."""
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GOOGLE_REVOKE_URL,
                params={"token": token},
                timeout=10.0,
            )
            response.raise_for_status()

    await _retry(_call)


# ---------------------------------------------------------------------------
# Gmail-specific functions
# ---------------------------------------------------------------------------

async def setup_gmail_watch(access_token: str, pubsub_topic: str) -> dict:
    """
    Sets up Gmail push notifications via Google Pub/Sub.
    Returns {historyId, expiration} from the Gmail watch response.
    """
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GMAIL_API_BASE}/watch",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "topicName": pubsub_topic,
                    "labelIds": ["INBOX"],
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    history_id = data.get("historyId")
    expiration = data.get("expiration")
    if not history_id:
        raise ValueError("Gmail watch setup returned empty historyId — watch may not be active")
    return {"historyId": history_id, "expiration": expiration}


async def stop_gmail_watch(access_token: str) -> None:
    """Stops Gmail push notifications."""
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GMAIL_API_BASE}/stop",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )
            response.raise_for_status()

    await _retry(_call)


async def list_messages_with_attachments(access_token: str, after_date: str) -> list:
    """
    Lists Gmail messages that have attachments after the given date.
    after_date format: YYYY/MM/DD (Gmail query syntax).
    Returns list of message stubs: [{id, threadId}].
    """
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GMAIL_API_BASE}/messages",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"q": f"has:attachment after:{after_date}"},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    messages = data.get("messages", [])
    if not isinstance(messages, list):
        raise ValueError("Gmail messages list returned unexpected format")
    return messages


async def get_message_parts(access_token: str, message_id: str) -> dict:
    """
    Fetches full Gmail message including all MIME parts.
    Returns the raw message dict with payload.parts for attachment extraction.
    """
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GMAIL_API_BASE}/messages/{message_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"format": "full"},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    return await _circuit.call(_retry, _call)


# ---------------------------------------------------------------------------
# Drive-specific functions
# ---------------------------------------------------------------------------

async def setup_drive_watch(
    access_token: str,
    channel_id: str,
    webhook_url: str,
) -> dict:
    """
    Sets up Google Drive push notifications for changes.
    Uses the Drive changes.watch API to receive webhook notifications.
    Returns channel metadata from Google.
    """
    async def _call():
        async with httpx.AsyncClient() as client:
            # First get the page token for change tracking
            token_resp = await client.get(
                f"{DRIVE_API_BASE}/changes/startPageToken",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )
            token_resp.raise_for_status()
            page_token = token_resp.json().get("startPageToken", "")

            response = await client.post(
                f"{DRIVE_API_BASE}/changes/watch",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                params={"pageToken": page_token},
                json={
                    "id": channel_id,
                    "type": "web_hook",
                    "address": webhook_url,
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    return await _circuit.call(_retry, _call)


async def get_gmail_attachment_bytes(access_token: str, message_id: str, attachment_id: str) -> bytes:
    """Download a Gmail attachment and return raw bytes. Gmail uses URL-safe base64."""
    import base64 as _base64

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GMAIL_API_BASE}/messages/{message_id}/attachments/{attachment_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    b64data = data.get("data", "")
    # Gmail pads with - and _ instead of + and /; pad to multiple of 4
    padded = b64data + "=" * ((4 - len(b64data) % 4) % 4)
    return _base64.urlsafe_b64decode(padded)


async def download_drive_file_bytes(access_token: str, file_id: str) -> bytes:
    """Download a Google Drive file's content as raw bytes."""
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{DRIVE_API_BASE}/files/{file_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"alt": "media"},
                timeout=60.0,
            )
            response.raise_for_status()
            return response.content

    return await _circuit.call(_retry, _call)


async def list_pdf_files(access_token: str) -> list:
    """
    Lists non-trashed PDF files in the connected Google Drive.
    Returns list of file metadata dicts: [{id, name, mimeType, ...}].
    """
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{DRIVE_API_BASE}/files",
                headers={"Authorization": f"Bearer {access_token}"},
                params={
                    "q": "mimeType='application/pdf' and trashed=false",
                    "fields": "files(id,name,mimeType,size,createdTime,modifiedTime)",
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    files = data.get("files", [])
    if not isinstance(files, list):
        raise ValueError("Drive files list returned unexpected format")
    return files
