"""
Microsoft Outlook (Graph API) client.
Handles OAuth 2.0 via the Microsoft identity platform, mail subscriptions,
and message/attachment retrieval.
"""
import asyncio
import random
from datetime import datetime, UTC, timedelta
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.encryption import decrypt_credentials, encrypt_credentials
from app.integrations.outlook.circuit_breaker import _circuit

logger = get_logger(__name__)

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
# Mail.Send is required to dispatch AR collection reminders from the connected mailbox.
# Adding it means existing Outlook connections must reconnect to grant the new scope.
OUTLOOK_SCOPES = "Mail.Read Mail.Send offline_access"
TOKEN_TTL_SECONDS = 3600  # Microsoft access tokens expire in 1 hour
SUBSCRIPTION_EXPIRY_MINUTES = 4230  # Maximum allowed by Microsoft Graph

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
                    "outlook_call_failed attempt=%d/%d retry_in=%.1fs",
                    attempt + 1, MAX_ATTEMPTS, wait,
                )
                await asyncio.sleep(wait)
    raise last_exc


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _auth_base_url() -> str:
    """Returns the Microsoft identity platform base URL using configured tenant_id."""
    settings = get_settings()
    return f"https://login.microsoftonline.com/{settings.microsoft_tenant_id}/oauth2/v2.0"


def build_auth_url(state: str) -> str:
    """
    Builds Microsoft OAuth authorization URL.
    Uses settings.microsoft_tenant_id (defaults to 'common' for multi-tenant).
    """
    settings = get_settings()
    params = {
        "client_id": settings.microsoft_client_id,
        "response_type": "code",
        "redirect_uri": settings.microsoft_redirect_uri,
        "scope": OUTLOOK_SCOPES,
        "response_mode": "query",
        "state": state,
    }
    return f"{_auth_base_url()}/authorize?{urlencode(params)}"


async def exchange_code(code: str, tenant_id: str) -> dict:
    """
    Exchanges OAuth authorization code for access + refresh tokens.
    Returns encrypted credentials dict with token_expiry_at.
    tenant_id is the Clendan internal tenant ID — used to derive the encryption key.
    """
    settings = get_settings()

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{_auth_base_url()}/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.microsoft_redirect_uri,
                    "client_id": settings.microsoft_client_id,
                    "client_secret": settings.microsoft_client_secret,
                    "scope": OUTLOOK_SCOPES,
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)

    expiry = (datetime.now(UTC) + timedelta(seconds=TOKEN_TTL_SECONDS)).isoformat()
    raw_creds = {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "token_expiry_at": expiry,
    }
    return encrypt_credentials(raw_creds, tenant_id)


async def refresh_outlook_token(refresh_token: str) -> dict:
    """
    Refreshes Microsoft access token using the stored refresh token (plaintext).
    Returns dict with access_token, refresh_token, token_expiry_at (all plaintext).
    Caller is responsible for re-encrypting before storage.
    """
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
                    "scope": OUTLOOK_SCOPES,
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


# ---------------------------------------------------------------------------
# Graph API helpers
# ---------------------------------------------------------------------------

async def get_user_info(access_token: str) -> dict:
    """
    GET /me — returns user display name and email address.
    Validates response before returning — empty response is not a success.
    """
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GRAPH_API_BASE}/me",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    if not data:
        raise ValueError("Microsoft Graph /me returned empty response — aborting")
    return {
        "display_name": data.get("displayName", ""),
        "email": data.get("mail") or data.get("userPrincipalName", ""),
    }


async def send_outlook_message(
    access_token: str, *, to: str, subject: str, body_text: str, reply_to: str | None = None
) -> dict:
    """Send a plain-text email from the connected Outlook account (POST /me/sendMail).
    Graph returns 202 Accepted with no body. Returns {message_id, thread_id}."""
    message: dict = {
        "subject": subject,
        "body": {"contentType": "Text", "content": body_text},
        "toRecipients": [{"emailAddress": {"address": to}}],
    }
    if reply_to:
        message["replyTo"] = [{"emailAddress": {"address": reply_to}}]

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GRAPH_API_BASE}/me/sendMail",
                json={"message": message, "saveToSentItems": True},
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                timeout=20.0,
            )
            response.raise_for_status()
            return response

    resp = await _circuit.call(_retry, _call)
    return {"message_id": resp.headers.get("request-id", ""), "thread_id": ""}


async def create_mail_subscription(
    access_token: str,
    notification_url: str,
    client_state: str,
) -> dict:
    """
    Creates a Graph API change notification subscription for new mail messages.
    resource: me/messages, changeType: created.
    Expiry: 4230 minutes from now (maximum allowed by Microsoft).
    Returns the full subscription dict including id and expirationDateTime.
    """
    expiry_dt = (datetime.now(UTC) + timedelta(minutes=SUBSCRIPTION_EXPIRY_MINUTES)).strftime(
        "%Y-%m-%dT%H:%M:%S.0000000Z"
    )

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GRAPH_API_BASE}/subscriptions",
                json={
                    "changeType": "created",
                    "notificationUrl": notification_url,
                    "resource": "me/messages",
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


async def renew_subscription(access_token: str, subscription_id: str) -> dict:
    """
    Renews an existing subscription by PATCHing its expirationDateTime.
    Returns the updated subscription dict.
    """
    expiry_dt = (datetime.now(UTC) + timedelta(minutes=SUBSCRIPTION_EXPIRY_MINUTES)).strftime(
        "%Y-%m-%dT%H:%M:%S.0000000Z"
    )

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{GRAPH_API_BASE}/subscriptions/{subscription_id}",
                json={"expirationDateTime": expiry_dt},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    return await _circuit.call(_retry, _call)


async def delete_subscription(access_token: str, subscription_id: str) -> None:
    """
    Deletes a Graph API subscription. Silently ignores 404 (already deleted).
    """
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


async def list_messages_with_attachments(
    access_token: str,
    filter_str: str | None = None,
) -> list:
    """
    GET /me/messages?$filter=hasAttachments eq true
    Applies an optional additional OData filter string.
    Returns list of message dicts.
    """
    base_filter = "hasAttachments eq true"
    combined_filter = f"{base_filter} and {filter_str}" if filter_str else base_filter
    params = urlencode({"$filter": combined_filter, "$top": "100"})

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GRAPH_API_BASE}/me/messages?{params}",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                timeout=20.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    return data.get("value", [])


async def get_message_attachments(access_token: str, message_id: str) -> list:
    """
    GET /me/messages/{id}/attachments
    Returns list of attachment dicts for the given message.
    """
    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GRAPH_API_BASE}/me/messages/{message_id}/attachments",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    return data.get("value", [])


async def get_attachment_bytes(
    access_token: str, message_id: str, attachment_id: str
) -> tuple[bytes, str]:
    """
    GET /me/messages/{id}/attachments/{attachmentId}
    Returns (raw_bytes, content_type). contentBytes is standard base64 in Graph API.
    """
    import base64 as _base64

    async def _call():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GRAPH_API_BASE}/me/messages/{message_id}/attachments/{attachment_id}",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    data = await _circuit.call(_retry, _call)
    content_bytes_b64 = data.get("contentBytes", "")
    content_type = data.get("contentType", "application/pdf")
    raw_bytes = _base64.b64decode(content_bytes_b64) if content_bytes_b64 else b""
    return raw_bytes, content_type
