"""
TrueLayer webhook receiver.
TrueLayer basic tier does not provide standard signature verification.
All valid POST requests are accepted; events are filtered by type.
"""
import json

from fastapi import APIRouter, HTTPException, Request

from app.core.db import get_db
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.orchestrator.events import enqueue_orchestrator_event

_logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/truelayer")
async def truelayer_webhook(request: Request):
    """
    Receives TrueLayer event notifications.
    No signature verification available in basic tier — all requests accepted.
    Emits orchestrator events for transaction events.
    """
    body = await request.body()

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    _logger.info("truelayer_webhook_received")

    event_type: str = payload.get("type", "")

    if event_type != "transaction":
        return standard_response(data={"received": True})

    db = get_db()
    integration = await db.integration.find_first(
        where={"type": "truelayer", "status": "connected"}
    )
    if not integration:
        _logger.warning("truelayer_webhook_no_integration")
        return standard_response(data={"received": True})

    tenant_id = integration.tenant_id
    event_data: dict = payload.get("data", {})
    transaction_id: str = event_data.get("transaction_id", "")
    idempotency_key = f"truelayer:transaction:{transaction_id}"

    execution_id = await enqueue_orchestrator_event(
        tenant_id=tenant_id,
        event_type="transaction_posted",
        payload={
            "source": "truelayer",
            "transaction_id": transaction_id,
            "amount_minor": int(abs(float(event_data.get("amount", 0))) * 100),
            "currency": event_data.get("currency", "GBP").upper(),
        },
        idempotency_key=idempotency_key,
        db=db,
    )

    if execution_id:
        _logger.info(
            "truelayer_event_queued",
            extra={
                "execution_id": execution_id,
                "transaction_id": transaction_id,
                "tenant_id": tenant_id,
            },
        )

    return standard_response(data={"received": True})
