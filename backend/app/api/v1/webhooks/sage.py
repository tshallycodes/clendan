"""
Sage Business Cloud webhook receiver.
Sage does not provide standard key-based signature verification in v1.
All valid POST requests are accepted; events are filtered by type.
"""
import json

from fastapi import APIRouter, HTTPException, Request

from app.core.db import get_db
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.events import enqueue_event

_logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_INVOICE_EVENT_TYPES = frozenset({"SalesInvoice.Posted", "PurchaseInvoice.Posted"})


@router.post("/sage")
async def sage_webhook(request: Request):
    """
    Receives Sage Business Cloud event notifications.
    No signature verification in v1 - Sage does not provide standard signing.
    Emits events for invoice events.
    """
    body = await request.body()

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    _logger.info("sage_webhook_received")

    event_type: str = payload.get("$eventType", "")
    entity_id: str = payload.get("$entity", "")

    if event_type not in _INVOICE_EVENT_TYPES:
        return standard_response(data={"received": True})

    db = get_db()
    integration = await db.integration.find_first(
        where={"type": "sage", "status": "connected"}
    )
    if not integration:
        _logger.warning("sage_webhook_no_integration")
        return standard_response(data={"received": True})

    tenant_id = integration.tenant_id
    idempotency_key = f"sage:{event_type}:{entity_id}"

    event_payload = {
        "source": "sage",
        "entity_type": event_type.split(".")[0],
        "entity_id": entity_id,
    }

    execution_id = await enqueue_event(
        tenant_id=tenant_id,
        event_type="invoice_received",
        payload=event_payload,
        idempotency_key=idempotency_key,
        db=db,
    )

    if execution_id:
        _logger.info(
            "sage_event_queued",
            extra={
                "execution_id": execution_id,
                "event_type": event_type,
                "tenant_id": tenant_id,
            },
        )

    return standard_response(data={"received": True})
