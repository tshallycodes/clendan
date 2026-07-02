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

_logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/truelayer")
async def truelayer_webhook(request: Request):
    """
    Receives TrueLayer event notifications.
    No signature verification available in basic tier — all requests accepted.
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

    event_data: dict = payload.get("data", {})
    _logger.info(
        "truelayer_event_accepted",
        extra={"transaction_id": event_data.get("transaction_id", "")},
    )

    return standard_response(data={"received": True})
