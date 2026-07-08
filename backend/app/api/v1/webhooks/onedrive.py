"""
Microsoft Graph change notification receiver for OneDrive.

Validation endpoint (GET):
  Microsoft sends GET with ?validationToken=... before activating a subscription.
  Must echo the token back as plain text with Content-Type text/plain and 200 OK.

Notification endpoint (POST):
  Receives change notifications when drive content changes.
  Must return 202 IMMEDIATELY - Microsoft retries if the response is slow.
  clientState is verified against tenant_id before any processing.
"""
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from app.core.db import get_db
from app.core.logging import get_logger

_logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/onedrive")
async def onedrive_webhook_validation(
    validation_token: str = Query(..., alias="validationToken"),
):
    """
    Microsoft Graph subscription validation endpoint for OneDrive.
    Must return the validationToken as plain text with 200 OK.
    """
    _logger.info("onedrive_webhook_validation_received")
    return PlainTextResponse(content=validation_token, status_code=200)


@router.post("/onedrive", status_code=status.HTTP_202_ACCEPTED)
async def onedrive_webhook(request: Request):
    """
    Receives Microsoft Graph change notifications for OneDrive drive changes.
    Returns 202 IMMEDIATELY.
    clientState is verified against stored tenant_id to prevent spoofed notifications.
    """
    try:
        payload = await request.json()
    except Exception:
        _logger.warning("onedrive_webhook_invalid_json")
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    notifications = payload.get("value", [])
    if not notifications:
        return {"accepted": True}

    db = get_db()

    for notification in notifications:
        subscription_id = notification.get("subscriptionId", "")
        client_state = notification.get("clientState", "")
        change_type = notification.get("changeType", "")

        if not subscription_id or not client_state:
            _logger.warning("onedrive_webhook_missing_fields subscription_id=%s", subscription_id)
            continue

        # client_state == tenant_id (set at subscription creation time)
        integration = await db.integration.find_first(
            where={"type": "onedrive", "status": "connected", "tenant_id": client_state}
        )
        if not integration:
            _logger.warning(
                "onedrive_webhook_no_integration subscription_id=%s client_state=%s",
                subscription_id, client_state,
            )
            continue

        _logger.info(
            "onedrive_webhook_notification_received",
            extra={
                "tenant_id": integration.tenant_id,
                "subscription_id": subscription_id,
                "change_type": change_type,
            },
        )

        try:
            from app.integrations.onedrive.sync import enqueue_onedrive_sync
            await enqueue_onedrive_sync(
                integration_id=integration.id,
                tenant_id=integration.tenant_id,
            )
        except Exception as exc:
            _logger.error(
                "onedrive_webhook_enqueue_failed tenant=%s: %s",
                integration.tenant_id, type(exc).__name__,
            )

    return {"accepted": True}
