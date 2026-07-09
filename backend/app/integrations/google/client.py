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
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"

TOKEN_TTL_SECONDS = 3600
TOKEN_EARLY_REFRESH_SECONDS = 60

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

async def _retry(fn, *args, **kwargs):
    """Exponential backoff with jitter. Raises on final failure."""
    last_exc: Exception | None = None
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
    assert last_exc is not None
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
    logger.info("google_exchange_code_start", extra={
        "tenant_id": tenant_id,
        "redirect_uri": redirect_uri,
        "token_url": GOOGLE_TOKEN_URL,
        "client_id": (settings.google_client_id[:12] + "...") if settings.google_client_id else "MISSING",
        "has_secret": bool(settings.google_client_secret),
        "code_len": len(code) if code else 0,
    })

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
            logger.info("google_exchange_code_response", extra={
                "tenant_id": tenant_id,
                "http_status": response.status_code,
                "has_error": "error" in response.text,
                "response_preview": response.text[:200] if response.status_code != 200 else "OK",
            })
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    logger.info("google_exchange_code_ok", extra={"tenant_id": tenant_id, "has_access_token": bool(data.get("access_token")), "has_refresh_token": bool(data.get("refresh_token"))})

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


async def list_messages_with_attachments(access_token: str, after_date: str, extra_query: str = "") -> list:
    """
    Lists Gmail messages that have attachments after the given date. ``extra_query`` is
    appended to the Gmail search (e.g. "label:Invoices" or "from:accounts@supplier.com")
    to scope which emails are ingested.
    after_date format: YYYY/MM/DD (Gmail query syntax).
    Returns list of message stubs: [{id, threadId}].
    """
    query = f"has:attachment after:{after_date}"
    if extra_query and extra_query.strip():
        query = f"{query} {extra_query.strip()}"

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GMAIL_API_BASE}/messages",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"q": query},
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


async def find_folder_ids_by_name(access_token: str, folder_name: str) -> list[str]:
    """
    Resolves a Drive folder name to ALL matching non-trashed folder IDs. Drive allows
    several folders to share a name, so every match is returned and the caller scopes
    listing to all of them - we never arbitrarily pick one. Returns [] if none match.
    Matching is exact per the Drive API.
    """
    name = (folder_name or "").strip().strip("/")
    if not name:
        return []
    escaped = name.replace("\\", "\\\\").replace("'", "\\'")

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{DRIVE_API_BASE}/files",
                headers={"Authorization": f"Bearer {access_token}"},
                params={
                    "q": (
                        "mimeType='application/vnd.google-apps.folder' "
                        f"and name='{escaped}' and trashed=false"
                    ),
                    "fields": "files(id,name)",
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    folders = data.get("files", []) or []
    return [f["id"] for f in folders if f.get("id")]


async def list_pdf_files(access_token: str, folder_ids: list[str] | None = None) -> list:
    """
    Lists non-trashed PDF files in the connected Google Drive. When ``folder_ids`` is
    provided, only PDFs directly inside any of those folders are returned (covers folders
    that share a name); otherwise every PDF in the drive is returned. Returns list of file
    metadata dicts: [{id, name, mimeType, ...}].
    """
    query = "mimeType='application/pdf' and trashed=false"
    if folder_ids:
        parents = " or ".join(f"'{fid}' in parents" for fid in folder_ids)
        query += f" and ({parents})"

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{DRIVE_API_BASE}/files",
                headers={"Authorization": f"Bearer {access_token}"},
                params={
                    "q": query,
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


async def upload_file_to_drive(access_token: str, pdf_bytes: bytes, filename: str) -> str:
    """Upload a PDF to Google Drive via multipart upload. Returns the created file's Drive ID."""
    import json as _json

    boundary = "clendan_upload"
    metadata = _json.dumps({"name": filename, "mimeType": "application/pdf"}).encode()
    body = (
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
        + metadata
        + f"\r\n--{boundary}\r\nContent-Type: application/pdf\r\n\r\n".encode()
        + pdf_bytes
        + f"\r\n--{boundary}--".encode()
    )

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": f"multipart/related; boundary={boundary}",
                },
                content=body,
                timeout=120.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    file_id = data.get("id", "")
    if not file_id:
        raise ValueError("Drive upload returned no file ID")
    return file_id


# ---------------------------------------------------------------------------
# Push notifications (changes.watch) - real-time new-file detection
# ---------------------------------------------------------------------------

async def get_changes_start_page_token(access_token: str) -> str:
    """Returns the Drive changes start page token, required to open a changes.watch channel."""
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{DRIVE_API_BASE}/changes/startPageToken",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    return data.get("startPageToken", "")


async def watch_drive_changes(
    access_token: str,
    *,
    channel_id: str,
    webhook_url: str,
    page_token: str,
    ttl_seconds: int | None = None,
) -> dict:
    """Open a Drive push-notification channel on the changes feed. Google POSTs to
    ``webhook_url`` whenever anything in the drive changes. Returns
    {resource_id, expiration} (expiration is epoch-ms as a string)."""
    channel: dict = {"id": channel_id, "type": "web_hook", "address": webhook_url}
    if ttl_seconds:
        channel["expiration"] = str(int((datetime.now(UTC).timestamp() + ttl_seconds) * 1000))

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{DRIVE_API_BASE}/changes/watch",
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                params={"pageToken": page_token},
                json=channel,
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    return {"resource_id": data.get("resourceId", ""), "expiration": data.get("expiration", "")}


async def stop_drive_channel(access_token: str, channel_id: str, resource_id: str) -> None:
    """Stop a Drive push-notification channel. Raises on hard failure (callers treat as best-effort)."""
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{DRIVE_API_BASE}/channels/stop",
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                json={"id": channel_id, "resourceId": resource_id},
                timeout=15.0,
            )
            response.raise_for_status()

    await _circuit.call(_retry, _call)
