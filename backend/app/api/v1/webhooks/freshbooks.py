"""
FreshBooks webhook receiver.
FreshBooks signs payloads with HMAC-SHA256; the signature is base64-encoded
in the X-Freshbooks-Hmac-Sha256 header. Verification must succeed before
any processing.
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
from app.events import enqueue_event

_logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _verify_freshbooks_signature(body: bytes, signature_header: str, secret: str) -> bool:
    """
    Verifies FreshBooks HMAC-SHA256 signature.
    FreshBooks sends: base64(HMAC-SHA256(raw_body, secret))
    """
    try:
        expected = base64.b64encode(
            hmac.new(secret.encode(), body, hashlib.sha256).digest()
        ).decode()
        return hmac.compare_digest(expected, signature_header)
    except Exception:
        return False


@router.post("/freshbooks")
async def freshbooks_webhook(
    request: Request,
    x_freshbooks_hmac_sha256: str = Header(None, alias="X-Freshbooks-Hmac-Sha256"),
):
    """
    Receives FreshBooks event notifications.
    Emits events for invoice events.
    """
    settings = get_settings()
    body = await request.body()

    if settings.freshbooks_webhook_secret:
        if not x_freshbooks_hmac_sha256:
            _logger.warning("freshbooks_webhook_missing_signature")
            raise HTTPException(status_code=401, detail="Missing webhook signature")
        if not _verify_freshbooks_signature(body, x_freshbooks_hmac_sha256, settings.freshbooks_webhook_secret):
            _logger.warning("freshbooks_webhook_invalid_signature")
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
    else:
        _logger.warning("freshbooks_webhook_secret_not_configured_skipping_verification")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    _logger.info("freshbooks_webhook_received")

    event_type: str = payload.get("name", "")
    data: dict = payload.get("object", {})

    if event_type not in ("invoice.create", "invoice.update"):
        return standard_response(data={"received": True})

    db = get_db()
    integration = await db.integration.find_first(
        where={"type": "freshbooks", "status": "connected"}
    )
    if not integration:
        _logger.warning("freshbooks_webhook_no_integration")
        return standard_response(data={"received": True})

    tenant_id = integration.tenant_id
    object_id = str(data.get("id", ""))
    idempotency_key = f"freshbooks:{event_type}:{object_id}"

    event_payload = {
        "source": "freshbooks",
        "invoice_id": object_id,
        "account_id": str(data.get("accountid", "")),
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
            "freshbooks_event_queued",
            extra={
                "execution_id": execution_id,
                "event_type": event_type,
                "tenant_id": tenant_id,
            },
        )

    return standard_response(data={"received": True})
