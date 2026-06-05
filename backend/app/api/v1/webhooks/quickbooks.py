"""
QuickBooks webhook receiver.
Intuit signs payloads with HMAC-SHA256 using the webhook verifier token.
Verification must succeed before any processing.
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

# QB entities that map to invoice_received events
_INVOICE_ENTITIES = frozenset({"Invoice", "Bill"})
_INVOICE_OPERATIONS = frozenset({"Create", "Update"})


def _verify_signature(body: bytes, signature: str, verifier_token: str) -> bool:
    expected = hmac.new(
        verifier_token.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/quickbooks")
async def quickbooks_webhook(
    request: Request,
    intuit_signature: str = Header(..., alias="intuit-signature"),
):
    """
    Receives QuickBooks entity-change notifications.
    Emits orchestrator events for Invoice/Bill creates and updates.
    """
    settings = get_settings()
    if not settings.quickbooks_webhook_verifier_token:
        _logger.error("quickbooks_webhook_verifier_token_not_configured")
        raise HTTPException(status_code=503, detail="Webhook verification not configured")

    body = await request.body()
    if not _verify_signature(body, intuit_signature, settings.quickbooks_webhook_verifier_token):
        _logger.warning("qb_webhook_invalid_signature")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    _logger.info("qb_webhook_received")

    db = get_db()

    for notification in payload.get("eventNotifications", []):
        realm_id = notification.get("realmId", "")
        if not realm_id:
            continue

        # Find QB integration for this realm_id
        integrations = await db.integration.find_many(
            where={"type": "quickbooks", "status": "connected"}
        )
        integration = next(
            (
                i for i in integrations
                if json.loads(i.encrypted_credentials).get("realm_id") == realm_id
            ),
            None,
        )
        if not integration:
            _logger.warning("qb_webhook_no_integration", extra={"realm_id": realm_id})
            continue

        tenant_id = integration.tenant_id
        entities = notification.get("dataChangeEvent", {}).get("entities", [])

        for entity in entities:
            entity_name = entity.get("name", "")
            operation = entity.get("operation", "")
            entity_id = entity.get("id", "")

            if entity_name not in _INVOICE_ENTITIES or operation not in _INVOICE_OPERATIONS:
                continue

            idempotency_key = f"qb:{realm_id}:{entity_name}:{entity_id}:{operation}"

            execution_id = await enqueue_orchestrator_event(
                tenant_id=tenant_id,
                event_type="invoice_received",
                payload={
                    "qb_entity": entity_name,
                    "qb_entity_id": entity_id,
                    "qb_operation": operation,
                    "realm_id": realm_id,
                    "integration_id": integration.id,
                },
                idempotency_key=idempotency_key,
                db=db,
            )

            if execution_id:
                _logger.info(
                    "qb_invoice_event_queued",
                    extra={
                        "execution_id": execution_id,
                        "entity": entity_name,
                        "entity_id": entity_id,
                        "tenant_id": tenant_id,
                    },
                )

    return standard_response(data={"received": True})
