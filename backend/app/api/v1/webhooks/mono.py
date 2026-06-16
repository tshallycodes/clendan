"""
Mono webhook handler.
Verifies HMAC-SHA512 signature, routes events to sync jobs.
"""
import hashlib
import hmac
import json

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["mono-webhooks"])


def _verify_signature(raw_body: bytes, signature: str) -> bool:
    """HMAC-SHA512 signature verification for Mono webhook payloads."""
    secret = get_settings().mono_webhook_secret
    if not secret:
        logger.warning("mono_webhook_secret not configured — skipping signature check")
        return True
    computed = hmac.new(secret.encode(), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(computed, signature)


@router.post("/webhooks/mono")
async def mono_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    mono_webhook_secret: str = Header(default="", alias="mono-webhook-secret"),
):
    """
    Receives Mono webhook events.
    Events handled:
      mono.events.account_connected   → marks integration connected
      mono.events.sync_completed      → triggers transaction sync
      mono.events.reauthorisation_required → marks integration as error
    """
    raw_body = await request.body()

    if not _verify_signature(raw_body, mono_webhook_secret):
        logger.warning("Mono webhook signature mismatch — rejected")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    event = payload.get("event", "")
    data = payload.get("data", {})
    account_id = data.get("account", "")

    logger.info("Mono webhook received: event=%s account=%s", event, account_id)

    if not account_id:
        return {"received": True}

    db = get_db()

    if event == "mono.events.account_connected":
        integration = await _find_integration_by_mono_id(db, account_id)
        if integration:
            await db.integration.update(
                where={"id": integration.id},
                data={"status": "connected"},
            )
            background_tasks.add_task(
                _enqueue_sync, integration.id, integration.tenant_id
            )

    elif event == "mono.events.sync_completed":
        integration = await _find_integration_by_mono_id(db, account_id)
        if integration and integration.status != "disconnected":
            background_tasks.add_task(
                _enqueue_sync, integration.id, integration.tenant_id
            )

    elif event == "mono.events.reauthorisation_required":
        integration = await _find_integration_by_mono_id(db, account_id)
        if integration:
            await db.integration.update(
                where={"id": integration.id},
                data={"status": "error"},
            )
            logger.warning(
                "Mono reauthorisation required for integration %s (tenant %s)",
                integration.id,
                integration.tenant_id,
            )

    return {"received": True}


async def _find_integration_by_mono_id(db, mono_account_id_plain: str):
    """Finds the integration whose encrypted account ID decrypts to the given plain account ID."""
    from app.core.encryption import decrypt

    integrations = await db.integration.find_many(
        where={"type": "mono", "status": {"not": "disconnected"}}
    )
    for intg in integrations:
        try:
            creds = json.loads(intg.encrypted_credentials or "{}")
            encrypted = creds.get("account_id", "")
            if encrypted and decrypt(encrypted) == mono_account_id_plain:
                return intg
        except Exception:
            continue
    return None


async def _enqueue_sync(integration_id: str, tenant_id: str) -> None:
    from app.integrations.mono.sync import enqueue_mono_sync
    await enqueue_mono_sync(integration_id, tenant_id)
