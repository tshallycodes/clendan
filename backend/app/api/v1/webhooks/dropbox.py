"""
Dropbox webhook receiver.

Verification (GET):
  Dropbox sends GET /webhooks/dropbox?challenge=xxx before activating.
  Must echo the challenge back as plain text with 200 OK.

Notification (POST):
  Dropbox sends POST with optional {list_folder: {accounts: [...]}} body.
  We ignore the body - enqueue a sync for all connected Dropbox integrations.
  Always return 200.
"""
from fastapi import APIRouter, Query, Request
from fastapi.responses import PlainTextResponse

from app.core.db import get_db
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.integrations.dropbox.sync import enqueue_dropbox_sync

_logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/dropbox")
async def dropbox_webhook_challenge(
    challenge: str = Query(...),
):
    """
    Dropbox webhook verification endpoint.
    Dropbox calls this with ?challenge=xxx before activating the webhook.
    Must return the challenge as plain text with 200 OK.
    """
    _logger.info("dropbox_webhook_challenge_received")
    return PlainTextResponse(content=challenge, status_code=200)


@router.post("/dropbox")
async def dropbox_webhook(request: Request):
    """
    Receives Dropbox change notifications.
    Dropbox does not include what changed - enqueue a full sync for every
    connected integration to detect new PDFs.
    Always returns 200.
    """
    # Body may contain account hints but we do not parse it - enqueue sync for all connected integrations.
    db = get_db()

    integrations = await db.integration.find_many(
        where={"type": "dropbox", "status": "connected"}
    )

    if not integrations:
        _logger.info("dropbox_webhook_no_active_integrations")
        return standard_response(data={"received": True})

    for integration in integrations:
        try:
            await enqueue_dropbox_sync(
                integration_id=integration.id,
                tenant_id=integration.tenant_id,
            )
            _logger.info(
                "dropbox_webhook_sync_enqueued integration_id=%s tenant_id=%s",
                integration.id, integration.tenant_id,
            )
        except Exception as exc:
            _logger.error(
                "dropbox_webhook_enqueue_failed integration_id=%s: %s",
                integration.id, type(exc).__name__,
            )

    return standard_response(data={"received": True})
