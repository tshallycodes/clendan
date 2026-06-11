"""
Square webhook receiver.
Square signs payloads via HMAC-SHA256 using the webhook signature key.
Signature verification must succeed before any processing.
"""
import json

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.integrations.square.client import parse_square_event_type, verify_square_signature
from app.orchestrator.events import enqueue_orchestrator_event

_logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/square")
async def square_webhook(
    request: Request,
    x_square_hmacsha256_signature: str = Header(
        ..., alias="x-square-hmacsha256-signature"
    ),
):
    """
    Receives Square event notifications.
    Emits orchestrator events for payment and invoice events.
    """
    settings = get_settings()
    if not settings.square_webhook_signature_key:
        _logger.error("square_webhook_signature_key_not_configured")
        raise HTTPException(status_code=503, detail="Webhook verification not configured")

    body = await request.body()
    notification_url = f"{settings.backend_base_url}/v1/webhooks/square"

    if not verify_square_signature(
        body, x_square_hmacsha256_signature, settings.square_webhook_signature_key, notification_url
    ):
        _logger.warning("square_webhook_invalid_signature")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    _logger.info("square_webhook_received")

    event_type: str = payload.get("type", "")
    event_id: str = payload.get("event_id", "")
    orchestrator_event = parse_square_event_type(event_type)

    if orchestrator_event is None:
        return standard_response(data={"received": True})

    db = get_db()

    integration = await db.integration.find_first(
        where={"type": "square", "status": "connected"}
    )
    if not integration:
        _logger.warning("square_webhook_no_integration")
        return standard_response(data={"received": True})

    tenant_id = integration.tenant_id
    square_object = payload.get("data", {}).get("object", {})

    # Extract the inner object (payment or invoice)
    inner = (
        square_object.get("payment")
        or square_object.get("invoice")
        or square_object
    )
    square_object_id: str = inner.get("id", "")
    idempotency_key = f"square:{event_id}"

    if orchestrator_event == "invoice_received":
        event_payload = {
            "square_event_type": event_type,
            "square_object_id": square_object_id,
        }
    else:
        money = inner.get("amount_money") or {}
        event_payload = {
            "square_event_type": event_type,
            "square_object_id": square_object_id,
            "amount_minor": money.get("amount", 0),
            "currency": (money.get("currency") or "USD").upper(),
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
            "square_event_queued",
            extra={
                "execution_id": execution_id,
                "event_type": event_type,
                "orchestrator_event": orchestrator_event,
                "tenant_id": tenant_id,
            },
        )

    return standard_response(data={"received": True})
