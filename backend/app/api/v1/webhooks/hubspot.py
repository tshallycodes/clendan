"""
HubSpot webhook receiver.
HubSpot signs payloads with HMAC-SHA256 using the client secret.
Signature header: X-Hubspot-Signature-V3.
Signing string: HTTP_METHOD + url + raw_body + timestamp.
"""
import hashlib
import hmac
import json

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.orchestrator.events import enqueue_orchestrator_event

_logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_DEAL_SUBSCRIPTION_TYPES = frozenset({"deal.creation", "deal.propertyChange"})


def _verify_hubspot_signature(
    body: bytes,
    signature_header: str,
    secret: str,
    method: str,
    url: str,
    timestamp: str,
) -> bool:
    """
    Verifies HubSpot V3 HMAC-SHA256 signature.
    Signing string: HTTP_METHOD + url + raw_body + timestamp
    """
    try:
        signing_string = method.upper() + url + body.decode(errors="replace") + timestamp
        expected = hmac.new(
            secret.encode(), signing_string.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header)
    except Exception:
        return False


@router.post("/hubspot")
async def hubspot_webhook(
    request: Request,
    x_hubspot_signature_v3: str = Header(None, alias="X-Hubspot-Signature-V3"),
    x_hubspot_request_timestamp: str = Header(None, alias="X-Hubspot-Request-Timestamp"),
):
    """
    Receives HubSpot subscription event notifications.
    Verifies HMAC-SHA256 V3 signature before processing.
    Emits orchestrator events for deal events only.
    """
    settings = get_settings()
    body = await request.body()

    if settings.hubspot_client_secret:
        if not x_hubspot_signature_v3 or not x_hubspot_request_timestamp:
            _logger.warning("hubspot_webhook_missing_signature_headers")
            raise HTTPException(status_code=401, detail="Missing webhook signature headers")
        url = str(request.url)
        if not _verify_hubspot_signature(
            body, x_hubspot_signature_v3, settings.hubspot_client_secret,
            request.method, url, x_hubspot_request_timestamp,
        ):
            _logger.warning("hubspot_webhook_invalid_signature")
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
    else:
        _logger.warning("hubspot_client_secret_not_configured_skipping_verification")

    try:
        events: list = json.loads(body)
        if not isinstance(events, list):
            events = [events]
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    _logger.info("hubspot_webhook_received")

    db = get_db()
    integration = await db.integration.find_first(
        where={"type": "hubspot", "status": "connected"}
    )
    if not integration:
        _logger.warning("hubspot_webhook_no_integration")
        return standard_response(data={"received": True})

    tenant_id = integration.tenant_id

    for event in events:
        subscription_type: str = event.get("subscriptionType", "")
        if subscription_type not in _DEAL_SUBSCRIPTION_TYPES:
            continue

        object_id = str(event.get("objectId", ""))
        event_id = str(event.get("eventId", ""))
        idempotency_key = f"hubspot:{event_id}:{object_id}"

        execution_id = await enqueue_orchestrator_event(
            tenant_id=tenant_id,
            event_type="invoice_received",
            payload={
                "source": "hubspot",
                "object_type": "deal",
                "object_id": object_id,
            },
            idempotency_key=idempotency_key,
            db=db,
        )

        if execution_id:
            _logger.info(
                "hubspot_event_queued",
                extra={
                    "execution_id": execution_id,
                    "subscription_type": subscription_type,
                    "object_id": object_id,
                    "tenant_id": tenant_id,
                },
            )

    return standard_response(data={"received": True})
