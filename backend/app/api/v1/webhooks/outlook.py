"""
Microsoft Graph change notification receiver.

Validation endpoint (GET):
  Microsoft sends a GET with ?validationToken=... before activating a subscription.
  Must echo the token back as plain text with Content-Type text/plain and 200 OK.

Notification endpoint (POST):
  Receives change notifications when new mail arrives.
  Must return 202 IMMEDIATELY - Microsoft retries if the response is slow.
  clientState is verified against tenant_id before any processing.
"""
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from app.core.db import get_db
from app.core.logging import get_logger
from app.core.responses import standard_response

_logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/outlook")
async def outlook_webhook_validation(
    validation_token: str = Query(..., alias="validationToken"),
):
    """
    Microsoft Graph subscription validation endpoint.
    Microsoft calls this with a validationToken before activating the subscription.
    Must return the token as plain text (Content-Type: text/plain) with 200 OK.
    """
    _logger.info("outlook_webhook_validation_received")
    return PlainTextResponse(content=validation_token, status_code=200)


@router.post("/outlook", status_code=status.HTTP_202_ACCEPTED)
async def outlook_webhook(request: Request):
    """
    Receives Microsoft Graph change notifications for new mail messages.
    Returns 202 IMMEDIATELY - Microsoft retries if response exceeds its timeout.
    clientState is verified against stored tenant_id to prevent spoofed notifications.
    """
    try:
        payload = await request.json()
    except Exception:
        _logger.warning("outlook_webhook_invalid_json")
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    notifications = payload.get("value", [])
    if not notifications:
        return {"accepted": True}

    db = get_db()

    for notification in notifications:
        subscription_id = notification.get("subscriptionId", "")
        client_state = notification.get("clientState", "")
        change_type = notification.get("changeType", "")
        resource = notification.get("resource", "")

        if not subscription_id or not client_state:
            _logger.warning("outlook_webhook_missing_fields subscription_id=%s", subscription_id)
            continue

        # client_state == tenant_id (set at subscription creation time)
        # Scope lookup to the specific tenant to enforce isolation
        integration = await db.integration.find_first(
            where={"type": "outlook", "status": "connected", "tenant_id": client_state}
        )
        if not integration:
            _logger.warning(
                "outlook_webhook_no_integration subscription_id=%s client_state=%s",
                subscription_id, client_state,
            )
            continue

        tenant_id = integration.tenant_id

        _logger.info(
            "outlook_webhook_notification_received",
            extra={
                "tenant_id": tenant_id,
                "subscription_id": subscription_id,
                "change_type": change_type,
                "resource": resource,
            },
        )

        # Enqueue processing of the new message notification
        if change_type == "created":
            try:
                from app.integrations.outlook.sync import enqueue_outlook_sync
                await enqueue_outlook_sync(
                    integration_id=integration.id,
                    tenant_id=tenant_id,
                )
            except Exception as exc:
                _logger.error(
                    "outlook_webhook_enqueue_failed tenant=%s: %s",
                    tenant_id, type(exc).__name__,
                )

    # 202 returned by status_code on decorator - response body is informational only
    return {"accepted": True}
