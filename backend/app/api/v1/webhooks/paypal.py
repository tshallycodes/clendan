"""
PayPal webhook receiver.
PayPal webhook verification uses the PayPal verify-webhook-signature API.
Verification must succeed before any processing.
"""
import json

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.integrations.paypal.client import parse_paypal_event_type, verify_paypal_webhook
from app.orchestrator.events import enqueue_orchestrator_event

_logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/paypal")
async def paypal_webhook(
    request: Request,
    paypal_transmission_id: str = Header(..., alias="paypal-transmission-id"),
    paypal_transmission_time: str = Header(..., alias="paypal-transmission-time"),
    paypal_cert_url: str = Header(..., alias="paypal-cert-url"),
    paypal_auth_algo: str = Header(..., alias="paypal-auth-algo"),
    paypal_transmission_sig: str = Header(..., alias="paypal-transmission-sig"),
):
    """
    Receives PayPal event notifications.
    Emits orchestrator events for invoice paid events.
    """
    settings = get_settings()
    if not settings.paypal_webhook_id:
        _logger.error("paypal_webhook_id_not_configured")
        raise HTTPException(status_code=503, detail="Webhook verification not configured")

    body = await request.body()

    headers = {
        "paypal-transmission-id": paypal_transmission_id,
        "paypal-transmission-time": paypal_transmission_time,
        "paypal-cert-url": paypal_cert_url,
        "paypal-auth-algo": paypal_auth_algo,
        "paypal-transmission-sig": paypal_transmission_sig,
    }

    if not await verify_paypal_webhook(body, headers, settings.paypal_webhook_id, settings):
        _logger.warning("paypal_webhook_invalid_signature")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    _logger.info("paypal_webhook_received")

    event_type: str = payload.get("event_type", "")
    event_id: str = payload.get("id", "")
    orchestrator_event = parse_paypal_event_type(event_type)

    if orchestrator_event is None:
        return standard_response(data={"received": True})

    db = get_db()

    integration = await db.integration.find_first(
        where={"type": "paypal", "status": "connected"}
    )
    if not integration:
        _logger.warning("paypal_webhook_no_integration")
        return standard_response(data={"received": True})

    tenant_id = integration.tenant_id
    resource = payload.get("resource", {})
    resource_id: str = resource.get("id", "")
    idempotency_key = f"paypal:{event_id}"

    event_payload = {
        "paypal_event_type": event_type,
        "paypal_resource_id": resource_id,
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
            "paypal_event_queued",
            extra={
                "execution_id": execution_id,
                "event_type": event_type,
                "orchestrator_event": orchestrator_event,
                "tenant_id": tenant_id,
            },
        )

    return standard_response(data={"received": True})
