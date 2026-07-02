"""
Adyen webhook receiver.
Adyen uses HMAC-SHA256 with a hex-encoded key; the signature is in
NotificationRequestItem.additionalData.hmacSignature.
Signing string: pspReference:originalReference:merchantAccountCode:
               merchantReference:amount.value:amount.currency:eventCode:success
Always responds with plain text "[accepted]" as Adyen requires exactly this body.
"""
import binascii
import hashlib
import hmac
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger

_logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_HANDLED_EVENT_CODES = frozenset({"AUTHORISATION", "REFUND", "CAPTURE"})


def _build_adyen_signing_string(item: dict) -> str:
    """Builds Adyen canonical signing string from a notification item."""
    amount = item.get("amount", {})
    fields = [
        item.get("pspReference", ""),
        item.get("originalReference", ""),
        item.get("merchantAccountCode", ""),
        item.get("merchantReference", ""),
        str(amount.get("value", "")),
        amount.get("currency", ""),
        item.get("eventCode", ""),
        item.get("success", ""),
    ]
    return ":".join(fields)


def _verify_adyen_signature(item: dict, hmac_key_hex: str) -> bool:
    """
    Verifies Adyen HMAC-SHA256 signature.
    Key is hex-decoded; signature is base64-encoded in additionalData.
    """
    try:
        import base64
        additional_data: dict = item.get("additionalData", {})
        provided_sig = additional_data.get("hmacSignature", "")
        key_bytes = binascii.unhexlify(hmac_key_hex)
        signing_string = _build_adyen_signing_string(item)
        expected = base64.b64encode(
            hmac.new(key_bytes, signing_string.encode("utf-8"), hashlib.sha256).digest()
        ).decode()
        return hmac.compare_digest(expected, provided_sig)
    except Exception:
        return False


@router.post("/adyen")
async def adyen_webhook(request: Request):
    """
    Receives Adyen notification events.
    Verifies HMAC-SHA256 signature per item when key is configured.
    Always responds with plain text '[accepted]' as required by Adyen.
    """
    settings = get_settings()
    body = await request.body()

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    _logger.info("adyen_webhook_received")

    notification_items: list = payload.get("notificationItems", [])
    db = get_db()

    integration = await db.integration.find_first(
        where={"type": "adyen", "status": "connected"}
    )
    if not integration:
        _logger.warning("adyen_webhook_no_integration")
        return PlainTextResponse("[accepted]")

    for wrapper in notification_items:
        item: dict = wrapper.get("NotificationRequestItem", {})

        if settings.adyen_webhook_hmac_key:
            if not _verify_adyen_signature(item, settings.adyen_webhook_hmac_key):
                _logger.warning(
                    "adyen_webhook_invalid_signature",
                    extra={"psp_reference": item.get("pspReference", "")},
                )
                continue
        else:
            _logger.warning("adyen_webhook_hmac_key_not_configured_skipping_verification")

        event_code: str = item.get("eventCode", "")
        success: str = item.get("success", "false")

        if event_code not in _HANDLED_EVENT_CODES:
            continue

        if event_code == "AUTHORISATION" and success != "true":
            continue

        _logger.info(
            "adyen_event_accepted",
            extra={"event_code": event_code, "psp_reference": item.get("pspReference", "")},
        )

    return PlainTextResponse("[accepted]")
