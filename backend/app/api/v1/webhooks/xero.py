"""
Xero webhook receiver.
Xero signs payloads with HMAC-SHA256 using the webhook signing key.
The signature is base64-encoded in the x-xero-signature header.
Verification must succeed before any processing.
"""
import base64
import hashlib
import hmac
import json

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.integrations.encryption import decrypt_credentials
from app.events import enqueue_event

_logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Xero event types that map to invoice_received
_INVOICE_RESOURCE_TYPES = frozenset({"Invoice"})


def _verify_xero_signature(body: bytes, signature_header: str, webhook_key: str) -> bool:
    """
    Verifies Xero HMAC-SHA256 signature.
    Xero sends: base64(HMAC-SHA256(raw_body, webhook_key))
    """
    try:
        expected_bytes = hmac.new(
            webhook_key.encode(),
            body,
            hashlib.sha256,
        ).digest()
        expected_b64 = base64.b64encode(expected_bytes).decode()
        return hmac.compare_digest(expected_b64, signature_header)
    except Exception:
        return False


@router.get("/xero/intent-to-receive")
async def xero_intent_to_receive():
    """
    Xero intent-to-receive validation endpoint.
    Xero sends a GET request to verify the endpoint exists and returns 200.
    """
    return standard_response(data={"ok": True})


@router.post("/xero")
async def xero_webhook(
    request: Request,
    x_xero_signature: str = Header(..., alias="x-xero-signature"),
):
    """
    Receives Xero entity-change notifications.
    Verifies HMAC-SHA256 signature before processing.
    Emits invoice_received events for Invoice ResourceUpdate events.
    """
    settings = get_settings()
    if not settings.xero_webhook_key:
        _logger.error("xero_webhook_key_not_configured")
        raise HTTPException(status_code=503, detail="Webhook verification not configured")

    body = await request.body()

    if not _verify_xero_signature(body, x_xero_signature, settings.xero_webhook_key):
        _logger.warning("xero_webhook_invalid_signature")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    _logger.info("xero_webhook_received")

    db = get_db()

    for event in payload.get("events", []):
        resource_type = event.get("resourceType", "")
        event_type = event.get("eventType", "")
        resource_id = event.get("resourceId", "")
        tenant_id_xero = event.get("tenantId", "")

        if not tenant_id_xero:
            continue

        # Only handle ResourceUpdate events for Invoice/Bill entities
        if resource_type not in _INVOICE_RESOURCE_TYPES or event_type != "ResourceUpdate":
            continue

        # Find the Clendan integration matching this Xero tenantId
        integrations = await db.integration.find_many(
            where={"type": "xero", "status": "connected"}
        )

        integration = None
        for i in integrations:
            try:
                creds = decrypt_credentials(i.encrypted_credentials, i.tenant_id)
                if creds.get("xero_tenant_id") == tenant_id_xero:
                    integration = i
                    break
            except Exception:
                continue

        if not integration:
            _logger.warning(
                "xero_webhook_no_integration xero_tenant_id=%s", tenant_id_xero
            )
            continue

        clendan_tenant_id = integration.tenant_id
        idempotency_key = f"xero:{tenant_id_xero}:{resource_type}:{resource_id}:{event_type}"

        execution_id = await enqueue_event(
            tenant_id=clendan_tenant_id,
            event_type="invoice_received",
            payload={
                "xero_resource_type": resource_type,
                "xero_resource_id": resource_id,
                "xero_event_type": event_type,
                "xero_tenant_id": tenant_id_xero,
                "integration_id": integration.id,
            },
            idempotency_key=idempotency_key,
            db=db,
        )

        if execution_id:
            _logger.info(
                "xero_invoice_event_queued",
                extra={
                    "execution_id": execution_id,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "tenant_id": clendan_tenant_id,
                },
            )

    return standard_response(data={"received": True})
