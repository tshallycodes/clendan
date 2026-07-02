"""
Wise webhook receiver.
Wise signature verification requires their RSA public key (complex; deferred to v2).
For v1: all POST requests are accepted with a logged warning. Events are filtered by type.
"""
import json

from fastapi import APIRouter, HTTPException, Request

from app.core.db import get_db
from app.core.logging import get_logger
from app.core.responses import standard_response

_logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/wise")
async def wise_webhook(request: Request):
    """
    Receives Wise event notifications.
    RSA signature verification is deferred to v2 — all requests accepted in v1.
    """
    _logger.warning(
        "wise_webhook_signature_verification_skipped_pending_rsa_implementation"
    )

    body = await request.body()

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    _logger.info("wise_webhook_received")

    event_type: str = payload.get("event_type", "")
    data: dict = payload.get("data", {})

    if event_type != "transfers#state-change":
        return standard_response(data={"received": True})

    if data.get("current_state") != "outgoing_payment_sent":
        return standard_response(data={"received": True})

    db = get_db()
    integration = await db.integration.find_first(
        where={"type": "wise", "status": "connected"}
    )
    if not integration:
        _logger.warning("wise_webhook_no_integration")
        return standard_response(data={"received": True})

    resource = data.get("resource", {})
    transfer_id = str(resource.get("id", ""))
    _logger.info(
        "wise_event_accepted",
        extra={"event_type": event_type, "transfer_id": transfer_id},
    )

    return standard_response(data={"received": True})
