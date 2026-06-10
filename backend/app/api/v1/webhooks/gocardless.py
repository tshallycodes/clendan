"""
GoCardless webhook receiver.
GoCardless signs payloads with HMAC-SHA256 using the webhook secret.
Signature must be verified before any processing.
"""
import hashlib
import hmac
import json

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.gocardless.sync import enqueue_gocardless_sync

_logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_HANDLED_EVENTS = frozenset({
    "payments.paid_out",
    "payments.failed",
    "mandates.cancelled",
})


def _verify_signature(payload: bytes, signature: str, webhook_secret: str) -> bool:
    expected = hmac.new(
        webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/gocardless")
async def gocardless_webhook(
    request: Request,
    webhook_signature: str = Header(..., alias="Webhook-Signature"),
):
    """
    Receives and verifies GoCardless event webhooks.
    Signature must be valid before any event is processed.
    Every received webhook is logged, including unhandled event types.
    """
    settings = get_settings()

    if not settings.gocardless_webhook_secret:
        _logger.error("gocardless_webhook_secret_not_configured")
        raise HTTPException(status_code=503, detail="Webhook verification not configured")

    payload = await request.body()

    if not _verify_signature(payload, webhook_signature, settings.gocardless_webhook_secret):
        _logger.warning("gocardless_webhook_invalid_signature")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    events = data.get("events", [])

    _logger.info(
        "gocardless_webhook_received",
        extra={"event_count": len(events)},
    )

    db = get_db()

    for event in events:
        resource_type: str = event.get("resource_type", "")
        action: str = event.get("action", "")
        event_id: str = event.get("id", "")
        event_key = f"{resource_type}.{action}"

        _logger.info(
            "gocardless_event",
            extra={"event_id": event_id, "event_key": event_key},
        )

        if event_key not in _HANDLED_EVENTS:
            # Log and continue — never reject unhandled events
            _logger.info(
                "gocardless_event_unhandled",
                extra={"event_id": event_id, "event_key": event_key},
            )
            continue

        # Find the GoCardless integration. GoCardless does not send a tenant identifier
        # in the payload, so we resolve via the connected integration.
        integration = await db.integration.find_first(
            where={"type": "gocardless", "status": "connected"}
        )
        if not integration:
            _logger.warning(
                "gocardless_webhook_no_integration",
                extra={"event_id": event_id, "event_key": event_key},
            )
            continue

        tenant_id = integration.tenant_id

        if event_key in ("payments.paid_out", "payments.failed"):
            # Enqueue a sync to pull the latest payment state
            try:
                await enqueue_gocardless_sync(
                    integration_id=integration.id,
                    tenant_id=tenant_id,
                )
                _logger.info(
                    "gocardless_sync_enqueued",
                    extra={"event_key": event_key, "tenant_id": tenant_id},
                )
            except Exception as exc:
                _logger.error(
                    "gocardless_webhook_enqueue_failed",
                    extra={"error": str(exc), "event_key": event_key},
                )

        elif event_key == "mandates.cancelled":
            # Enqueue sync to reflect cancelled mandate state
            try:
                await enqueue_gocardless_sync(
                    integration_id=integration.id,
                    tenant_id=tenant_id,
                )
                _logger.info(
                    "gocardless_mandate_cancelled_sync_enqueued",
                    extra={"tenant_id": tenant_id},
                )
            except Exception as exc:
                _logger.error(
                    "gocardless_webhook_enqueue_failed",
                    extra={"error": str(exc), "event_key": event_key},
                )

    return JSONResponse({"status": "ok"})
