"""
NetSuite SuiteCloud webhook receiver.
No signature verification in v1 - endpoint accepts all POST requests.
Emits invoice_received events for invoice/bill/PO record changes.
"""
from fastapi import APIRouter, Request

from app.core.db import get_db
from app.core.logging import get_logger
from app.events import enqueue_event

_logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_INVOICE_RECORD_TYPES = frozenset({"invoice", "vendorbill", "purchaseorder"})


@router.post("/netsuite")
async def netsuite_webhook(request: Request):
    """
    Receives NetSuite SuiteCloud push notifications.
    Emits invoice_received events for invoice, vendorbill, and purchaseOrder changes.
    Returns 200 immediately - no signature verification in v1.
    """
    try:
        body = await request.json()
    except Exception:
        _logger.warning("netsuite_webhook_invalid_json")
        return {"accepted": True}

    record_type = (body.get("recordType") or "").lower()
    record_id = body.get("recordId", "")

    _logger.info(
        "netsuite_webhook_received record_type=%s record_id=%s",
        record_type, record_id,
    )

    if record_type not in _INVOICE_RECORD_TYPES:
        return {"accepted": True}

    db = get_db()

    # Resolve tenant: use tenantId from body if present, else first connected netsuite integration
    tenant_id = body.get("tenantId", "")
    integration = None

    if tenant_id:
        integration = await db.integration.find_first(
            where={"tenant_id": tenant_id, "type": "netsuite", "status": "connected"}
        )
    else:
        integration = await db.integration.find_first(
            where={"type": "netsuite", "status": "connected"}
        )

    if not integration:
        _logger.warning(
            "netsuite_webhook_no_integration record_type=%s record_id=%s",
            record_type, record_id,
        )
        return {"accepted": True}

    idempotency_key = f"netsuite:webhook:{record_type}:{record_id}"

    try:
        execution_id = await enqueue_event(
            tenant_id=integration.tenant_id,
            event_type="invoice_received",
            payload={
                "source": "netsuite",
                "record_type": record_type,
                "record_id": record_id,
            },
            idempotency_key=idempotency_key,
            db=db,
        )
        if execution_id:
            _logger.info(
                "netsuite_webhook_event_queued execution_id=%s record_type=%s record_id=%s",
                execution_id, record_type, record_id,
            )
    except Exception as exc:
        _logger.error(
            "netsuite_webhook_event_failed record_type=%s record_id=%s: %s",
            record_type, record_id, type(exc).__name__,
        )

    return {"accepted": True}
