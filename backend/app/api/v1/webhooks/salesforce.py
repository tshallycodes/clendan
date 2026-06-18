"""
Salesforce webhook / outbound message receiver.
Accepts REST notification callbacks from Salesforce Connected App.
No signature verification — Salesforce IPs are allowlisted at network layer.
Always returns 200 to prevent Salesforce retry storms.
"""
import json

from fastapi import APIRouter, Request

from app.core.db import get_db
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.orchestrator.events import enqueue_orchestrator_event

_logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/salesforce")
async def salesforce_webhook(request: Request):
    """
    Receives Salesforce outbound REST notifications.
    Routes Invoice/Opportunity events → invoice_received.
    Routes Payment events → transaction_posted.
    Always returns 200 regardless of processing outcome.
    """
    try:
        body = await request.body()
        payload: dict = json.loads(body)
    except (json.JSONDecodeError, Exception):
        _logger.warning("salesforce_webhook_invalid_body")
        return standard_response(data={"received": True})

    event_type_raw: str = payload.get("type", "")
    sobject: dict = payload.get("sobject", {})

    _logger.info("salesforce_webhook_received type=%s", event_type_raw)

    db = get_db()
    integration = await db.integration.find_first(
        where={"type": "salesforce", "status": "connected"}
    )
    if not integration:
        _logger.warning("salesforce_webhook_no_integration")
        return standard_response(data={"received": True})

    tenant_id = integration.tenant_id

    # Determine orchestrator event type
    if any(kw in event_type_raw for kw in ("Invoice", "Opportunity")):
        orchestrator_event = "invoice_received"
    elif "Payment" in event_type_raw:
        orchestrator_event = "transaction_posted"
    else:
        _logger.info("salesforce_webhook_unhandled_type type=%s", event_type_raw)
        return standard_response(data={"received": True})

    object_id = str(sobject.get("Id", ""))
    idempotency_key = f"salesforce:{event_type_raw}:{object_id}"

    try:
        execution_id = await enqueue_orchestrator_event(
            tenant_id=tenant_id,
            event_type=orchestrator_event,
            payload={
                "source": "salesforce",
                "object_type": event_type_raw,
                "object_id": object_id,
                "sobject": sobject,
            },
            idempotency_key=idempotency_key,
            db=db,
        )
        if execution_id:
            _logger.info(
                "salesforce_event_queued",
                extra={
                    "execution_id": execution_id,
                    "event_type": orchestrator_event,
                    "object_id": object_id,
                    "tenant_id": tenant_id,
                },
            )
    except Exception as exc:
        _logger.error(
            "salesforce_webhook_enqueue_failed event_type=%s error=%s",
            orchestrator_event,
            type(exc).__name__,
        )

    return standard_response(data={"received": True})
