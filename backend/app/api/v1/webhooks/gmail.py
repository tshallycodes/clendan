"""
Gmail webhook receiver — Google Pub/Sub push notifications.
Google sends base64-encoded JSON payloads. No signature to verify here;
security is provided by the HTTPS push endpoint URL being secret.
Always return 200 — Pub/Sub retries on any non-2xx response.
"""
import base64
import json

from fastapi import APIRouter, HTTPException, Request

from app.core.db import get_db
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.integrations.google.sync_gmail import enqueue_gmail_sync

_logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/gmail")
async def gmail_webhook(request: Request):
    """
    Receives Google Pub/Sub push notifications for Gmail.
    Payload structure: {message: {data: <base64_json>, messageId, publishTime}, subscription}.
    Decoded data contains: {emailAddress, historyId}.
    Enqueues a Gmail sync for all connected Gmail integrations matching the email.
    Always returns 200 — Pub/Sub retries on non-2xx.
    """
    try:
        body = await request.json()
    except Exception:
        # Malformed body — still return 200 to prevent infinite Pub/Sub retry
        _logger.warning("gmail_webhook_invalid_json")
        return standard_response(data={"received": True})

    message = body.get("message", {})
    raw_data = message.get("data", "")

    if not raw_data:
        _logger.warning("gmail_webhook_empty_data")
        return standard_response(data={"received": True})

    try:
        decoded = base64.b64decode(raw_data)
        content = json.loads(decoded)
    except Exception as exc:
        _logger.warning("gmail_webhook_decode_failed: %s", type(exc).__name__)
        return standard_response(data={"received": True})

    email_address = content.get("emailAddress", "")
    history_id = content.get("historyId", "")

    _logger.info(
        "gmail_webhook_received email=%s history_id=%s",
        email_address, history_id,
    )

    db = get_db()

    # Find all connected Gmail integrations and enqueue sync
    integrations = await db.integration.find_many(
        where={"type": "gmail", "status": "connected"}
    )

    if not integrations:
        _logger.info("gmail_webhook_no_active_integrations")
        return standard_response(data={"received": True})

    for integration in integrations:
        try:
            await enqueue_gmail_sync(
                integration_id=integration.id,
                tenant_id=integration.tenant_id,
            )
            _logger.info(
                "gmail_webhook_sync_enqueued integration_id=%s tenant_id=%s",
                integration.id, integration.tenant_id,
            )
        except Exception as exc:
            _logger.error(
                "gmail_webhook_enqueue_failed integration_id=%s: %s",
                integration.id, type(exc).__name__,
            )

    return standard_response(data={"received": True})
