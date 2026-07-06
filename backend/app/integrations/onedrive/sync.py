"""
OneDrive sync job — runs via arq worker.
Creates Graph API drive subscription, lists PDF files, emits receipt_received events.
The 'onedrive' source is handled in app/tool.py (run_receipt_received_job / run_document_received_job).
"""
import base64
import time
from datetime import datetime, UTC

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.encryption import decrypt_credentials, encrypt_credentials
from app.integrations.onedrive import client as onedrive

logger = get_logger(__name__)


async def sync_onedrive_connection(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: creates Graph drive subscription, lists PDF files,
    emits receipt_received events (idempotent), writes sync log, marks connected.
    Returns sync result dict.
    """
    db = get_db()
    settings = get_settings()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration:
        logger.warning("onedrive_sync_skipped_not_found integration_id=%s", integration_id)
        return {"status": "skipped", "reason": "not_found"}

    if integration.tenant_id != tenant_id:
        logger.error("onedrive_sync_tenant_mismatch integration_id=%s", integration_id)
        return {"status": "error", "reason": "tenant_mismatch"}

    if integration.status not in ("syncing", "connected"):
        logger.warning(
            "onedrive_sync_skipped_bad_status integration_id=%s status=%s",
            integration_id, integration.status,
        )
        return {"status": "skipped", "reason": "unexpected_status"}

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    except ValueError as exc:
        logger.error("onedrive_sync_decrypt_failed integration_id=%s: %s", integration_id, type(exc).__name__)
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        return {"status": "error", "reason": "decrypt_failed"}

    access_token = creds.get("access_token", "")
    if not access_token:
        logger.error("onedrive_sync_no_access_token integration_id=%s", integration_id)
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        return {"status": "error", "reason": "missing_access_token"}

    # Refresh token if expired
    token_expiry_at = creds.get("token_expiry_at")
    if token_expiry_at:
        try:
            if datetime.fromisoformat(token_expiry_at) <= datetime.now(UTC):
                logger.info("onedrive_token_expired_refreshing integration_id=%s", integration_id)
                new_tokens = await onedrive.refresh_onedrive_token(creds.get("refresh_token", ""))
                creds = {**creds, **new_tokens}
                access_token = new_tokens["access_token"]
                await db.integration.update(
                    where={"id": integration_id},
                    data={"encrypted_credentials": encrypt_credentials(creds, tenant_id)},
                )
        except Exception as exc:
            logger.error("onedrive_token_refresh_failed integration_id=%s: %s", integration_id, type(exc).__name__)

    # ---------------------------------------------------------------------------
    # Create drive change subscription
    # ---------------------------------------------------------------------------
    notification_url = f"{settings.backend_base_url}/v1/webhooks/onedrive"
    client_state = tenant_id

    subscription_id = creds.get("subscription_id", "")
    try:
        subscription = await onedrive.create_subscription(
            access_token=access_token,
            notification_url=notification_url,
            client_state=client_state,
        )
        subscription_id = subscription["id"]
        creds["subscription_id"] = subscription_id
        creds["subscription_expiry"] = subscription.get("expirationDateTime", "")
        await db.integration.update(
            where={"id": integration_id},
            data={"encrypted_credentials": encrypt_credentials(creds, tenant_id)},
        )
        logger.info("onedrive_subscription_created integration_id=%s subscription_id=%s", integration_id, subscription_id)
    except Exception as exc:
        logger.error(
            "onedrive_subscription_create_failed integration_id=%s: %s",
            integration_id, type(exc).__name__,
        )

    # ---------------------------------------------------------------------------
    # List PDF files
    # ---------------------------------------------------------------------------
    initial_status = integration.status
    sync_start = time.monotonic()
    sync_status = "success"
    file_count = 0
    files: list = []

    try:
        files = await onedrive.list_pdf_files(access_token)
        file_count = len(files)
        logger.info("onedrive_pdf_files_found integration_id=%s count=%d", integration_id, file_count)
    except Exception as exc:
        logger.error("onedrive_sync_list_failed integration_id=%s: %s", integration_id, type(exc).__name__)
        sync_status = "error"

    elapsed_ms = int((time.monotonic() - sync_start) * 1000)

    await db.integrationsynclog.create(data={
        "tenant_id": tenant_id,
        "integration_id": integration_id,
        "entity_type": "files",
        "status": sync_status,
        "records_synced": file_count,
        "duration_ms": elapsed_ms,
    })

    # Re-read to check for disconnection during sync
    current = await db.integration.find_unique(where={"id": integration_id})
    if not current or current.status == "disconnected":
        logger.info("onedrive_sync_aborted_disconnected integration_id=%s", integration_id)
        return {"status": "skipped", "reason": "disconnected_during_sync"}

    await db.integration.update(
        where={"id": integration_id},
        data={"status": "connected", "connected_at": datetime.now(UTC)},
    )

    if sync_status != "success":
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        return {"status": "error", "reason": "sync_failed"}

    if initial_status == "connected" and files:
        from app.events import enqueue_event
        _MAX_BYTES = 10 * 1024 * 1024
        for f in files:
            file_id = f.get("id", "")
            if not file_id:
                continue
            idempotency_key = f"onedrive:document:{file_id}"
            existing = await db.execution.find_first(
                where={"input_ref": idempotency_key, "tenant_id": tenant_id}
            )
            if existing:
                continue
            try:
                file_bytes = await onedrive.download_file(access_token, file_id)
            except Exception as exc:
                logger.warning("onedrive_file_download_failed file_id=%s: %s", file_id, type(exc).__name__)
                continue
            if len(file_bytes) > _MAX_BYTES:
                logger.warning("onedrive_file_too_large file_id=%s size=%d", file_id, len(file_bytes))
                continue
            try:
                await enqueue_event(
                    tenant_id=tenant_id,
                    event_type="document_received",
                    payload={
                        "source": "onedrive",
                        "integration_id": integration_id,
                        "file_id": file_id,
                        "filename": f.get("name", ""),
                        "file_bytes": base64.b64encode(file_bytes).decode(),
                        "content_type": "application/pdf",
                    },
                    idempotency_key=idempotency_key,
                    db=db,
                )
            except Exception as exc:
                logger.error("onedrive_document_event_failed file_id=%s: %s", file_id, type(exc).__name__)

    logger.info(
        "onedrive_sync_ok tenant=%s files=%d elapsed_ms=%d",
        tenant_id, file_count, elapsed_ms,
    )
    return {
        "status": "ok",
        "files_found": file_count,
        "subscription_id": subscription_id,
    }


async def enqueue_onedrive_sync(integration_id: str, tenant_id: str) -> None:
    """Enqueues a OneDrive sync job onto the arq Redis queue."""
    from app.queue.pool import get_queue_pool
    pool = await get_queue_pool()
    await pool.enqueue_job("sync_onedrive_connection", integration_id, tenant_id)
