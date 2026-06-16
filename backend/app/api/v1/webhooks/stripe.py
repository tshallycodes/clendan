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

    # Build event payload — extract fields relevant to each workflow
    base = {"stripe_event_type": event_type, "stripe_object_id": stripe_object_id}

    if orchestrator_event in ("invoice_received", "invoice_payment_failed"):
        event_payload = {
            **base,
            "amount_minor": stripe_object.get("amount_due", 0),
            "currency": (stripe_object.get("currency") or "usd").upper(),
            "customer": stripe_object.get("customer") or "",
        }
    elif orchestrator_event in ("transaction_posted", "charge_refunded"):
        event_payload = {
            **base,
            "amount_minor": stripe_object.get("amount_refunded" if orchestrator_event == "charge_refunded" else "amount", 0),
            "currency": (stripe_object.get("currency") or "usd").upper(),
        }
    elif orchestrator_event == "dispute_created":
        evidence = stripe_object.get("evidence_details") or {}
        event_payload = {
            **base,
            "amount_minor": stripe_object.get("amount", 0),
            "currency": (stripe_object.get("currency") or "usd").upper(),
            "charge_id": stripe_object.get("charge") or "",
            "reason": stripe_object.get("reason") or "",
            "due_by": evidence.get("due_by"),
        }
    elif orchestrator_event == "dispute_closed":
        event_payload = {
            **base,
            "status": stripe_object.get("status") or "",
            "amount_minor": stripe_object.get("amount", 0),
            "currency": (stripe_object.get("currency") or "usd").upper(),
        }
    elif orchestrator_event in ("payout_received", "payout_failed"):
        event_payload = {
            **base,
            "amount_minor": stripe_object.get("amount", 0),
            "currency": (stripe_object.get("currency") or "usd").upper(),
            "arrival_date": stripe_object.get("arrival_date"),
            "failure_message": stripe_object.get("failure_message") or "",
        }
    else:
        event_payload = base

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
