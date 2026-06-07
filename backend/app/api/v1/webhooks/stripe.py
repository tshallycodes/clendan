"""
Stripe webhook receiver.
Stripe signs payloads via HMAC-SHA256 using the webhook endpoint secret.
Signature verification must succeed before any processing.
"""
import json

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.integrations.stripe.client import parse_stripe_event_type, verify_stripe_signature
from app.orchestrator.events import enqueue_orchestrator_event

_logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(..., alias="stripe-signature"),
):
    """
    Receives Stripe event notifications.
    Emits orchestrator events for invoice and transaction events.
    """
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        _logger.error("stripe_webhook_secret_not_configured")
        raise HTTPException(status_code=503, detail="Webhook verification not configured")

    body = await request.body()
    if not verify_stripe_signature(body, stripe_signature, settings.stripe_webhook_secret):
        _logger.warning("stripe_webhook_invalid_signature")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    _logger.info("stripe_webhook_received")

    event_type: str = payload.get("type", "")
    event_id: str = payload.get("id", "")
    orchestrator_event = parse_stripe_event_type(event_type)

    if orchestrator_event is None:
        # Silently accept unhandled event types — Stripe sends many we don't use
        return standard_response(data={"received": True})

    db = get_db()

    integration = await db.integration.find_first(
        where={"type": "stripe", "status": "connected"}
    )
    if not integration:
        # May be an initial webhook test from the Stripe dashboard
        _logger.warning("stripe_webhook_no_integration")
        return standard_response(data={"received": True})

    tenant_id = integration.tenant_id
    stripe_object = payload.get("data", {}).get("object", {})
    stripe_object_id: str = stripe_object.get("id", "")
    idempotency_key = f"stripe:{event_id}"

    # Build event payload based on orchestrator event type
    if orchestrator_event == "invoice_received":
        event_payload = {
            "stripe_event_type": event_type,
            "stripe_object_id": stripe_object_id,
        }
    else:
        # transaction_posted — include amount and currency
        event_payload = {
            "stripe_event_type": event_type,
            "stripe_object_id": stripe_object_id,
            "amount_minor": stripe_object.get("amount", 0),
            "currency": stripe_object.get("currency", "usd").upper(),
        }

    execution_id = await enqueue_orchestrator_event(
        tenant_id=tenant_id,
        event_type=orchestrator_event,
        payload=event_payload,
        idempotency_key=idempotency_key,
        db=db,
    )

    if execution_id:
        _logger.info(
            "stripe_event_queued",
            extra={
                "execution_id": execution_id,
                "event_type": event_type,
                "orchestrator_event": orchestrator_event,
                "tenant_id": tenant_id,
            },
        )

    return standard_response(data={"received": True})
