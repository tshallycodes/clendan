"""
Google Drive webhook receiver - Drive push notification channel.
Google sends notifications via HTTP headers; no body signature to verify.
Security is provided by the channel ID and HTTPS endpoint URL.
Always return 200.
"""
from fastapi import APIRouter, Request

from app.core.db import get_db
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.integrations.google.sync_drive import enqueue_drive_sync

_logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Drive resource states that indicate new data is available
_ACTIONABLE_STATES = frozenset({"change", "sync"})


@router.post("/google-drive")
async def google_drive_webhook(request: Request):
    """
    Receives Google Drive push notification channel events.
    Relevant headers:
      X-Goog-Channel-ID  - the channel ID we supplied on watch setup
      X-Goog-Resource-State - "sync" (initial handshake) or "change" (new change)
      X-Goog-Resource-ID - opaque resource identifier
    On "change" or "sync" states: enqueues a Drive sync for all connected integrations.
    Always returns 200.
    """
    channel_id = request.headers.get("X-Goog-Channel-ID", "")
    resource_state = request.headers.get("X-Goog-Resource-State", "")
    resource_id = request.headers.get("X-Goog-Resource-ID", "")

    _logger.info(
        "drive_webhook_received channel_id=%s state=%s resource_id=%s",
        channel_id, resource_state, resource_id,
    )

    if resource_state not in _ACTIONABLE_STATES:
        _logger.info("drive_webhook_ignored_state state=%s", resource_state)
        return standard_response(data={"received": True})

    db = get_db()

    # Find all connected Drive integrations and enqueue sync
    integrations = await db.integration.find_many(
        where={"type": "google_drive", "status": "connected"}
    )

    if not integrations:
        _logger.info("drive_webhook_no_active_integrations")
        return standard_response(data={"received": True})

    for integration in integrations:
        try:
            await enqueue_drive_sync(
                integration_id=integration.id,
                tenant_id=integration.tenant_id,
            )
            _logger.info(
                "drive_webhook_sync_enqueued integration_id=%s tenant_id=%s",
                integration.id, integration.tenant_id,
            )
        except Exception as exc:
            _logger.error(
                "drive_webhook_enqueue_failed integration_id=%s: %s",
                integration.id, type(exc).__name__,
            )

    return standard_response(data={"received": True})
