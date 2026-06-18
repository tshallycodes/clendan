"""
SAP S/4HANA Cloud push notification receiver.
Accepts inbound event notifications from SAP Business Event Handling.
Always returns 200 to prevent SAP retry storms.
"""
import json

from fastapi import APIRouter, Request

from app.core.db import get_db
from app.core.logging import get_logger
from app.orchestrator.events import enqueue_orchestrator_event

logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/sap")
async def sap_webhook(request: Request):
    """
    Receives SAP S/4HANA Cloud push notifications.
    Routes SUPPLIER_INVOICE events → invoice_received orchestrator event.
    All other SAPObjectTypes are logged and silently accepted.
    Always returns 200 regardless of processing outcome.
    """
    try:
        body_bytes = await request.body()
        body: dict = json.loads(body_bytes)
    except (json.JSONDecodeError, Exception):
        logger.warning("sap_webhook_invalid_body")
        return {"accepted": True}

    sap_object_type: str = body.get("SAPObjectType", "")
    sap_object_id: str = body.get("SAPObjectID", "")

    logger.info(
        "sap_webhook_received object_type=%s object_id=%s",
        sap_object_type, sap_object_id,
    )

    if sap_object_type == "SUPPLIER_INVOICE" and sap_object_id:
        db = get_db()
        integration = await db.integration.find_first(
            where={"type": "sap", "status": "connected"}
        )
        if not integration:
            logger.warning("sap_webhook_no_connected_integration object_id=%s", sap_object_id)
            return {"accepted": True}

        try:
            execution_id = await enqueue_orchestrator_event(
                tenant_id=integration.tenant_id,
                event_type="invoice_received",
                payload={
                    "source": "sap",
                    "invoice_id": sap_object_id,
                    "event_type": body.get("EventType", ""),
                },
                idempotency_key=f"sap:webhook:invoice:{sap_object_id}",
                db=db,
            )
            if execution_id:
                logger.info(
                    "sap_webhook_invoice_queued execution_id=%s invoice_id=%s",
                    execution_id, sap_object_id,
                )
        except Exception as exc:
            logger.error(
                "sap_webhook_enqueue_failed object_id=%s error=%s",
                sap_object_id, type(exc).__name__,
            )
    else:
        logger.info(
            "sap_webhook_unhandled_object_type object_type=%s object_id=%s",
            sap_object_type, sap_object_id,
        )

    return {"accepted": True}
