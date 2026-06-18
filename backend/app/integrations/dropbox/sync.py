"""
Dropbox sync job — runs via arq worker.
Lists PDF files, checks idempotency, emits receipt_received events, writes sync log.
"""
import time
from datetime import datetime, UTC

from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.encryption import decrypt_credentials, encrypt_credentials
from app.integrations.dropbox import client as dropbox

logger = get_logger(__name__)


async def sync_dropbox_connection(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: list PDF files in Dropbox, emit receipt_received events (idempotent),
    write sync log, mark integration as connected.
    Returns sync result dict.
    """
    db = get_db()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration:
        logger.warning("dropbox_sync_skipped_not_found integration_id=%s", integration_id)
        return {"status": "skipped", "reason": "not_found"}

    if integration.tenant_id != tenant_id:
        logger.error("dropbox_sync_tenant_mismatch integration_id=%s", integration_id)
        return {"status": "error", "reason": "tenant_mismatch"}

    if integration.status not in ("syncing", "connected"):
        logger.warning(
            "dropbox_sync_skipped_bad_status integration_id=%s status=%s",
            integration_id, integration.status,
        )
        return {"status": "skipped", "reason": "unexpected_status"}

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    except ValueError as exc:
        logger.error("dropbox_sync_decrypt_failed integration_id=%s: %s", integration_id, type(exc).__name__)
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        return {"status": "error", "reason": "decrypt_failed"}

    access_token = creds.get("access_token", "")
    refresh_token_val = creds.get("refresh_token", "")

    # Refresh token if expired
    token_expiry_at = creds.get("token_expiry_at")
    if token_expiry_at:
        try:
            if datetime.fromisoformat(token_expiry_at) <= datetime.now(UTC):
                logger.info("dropbox_token_expired_refreshing integration_id=%s", integration_id)
                new_tokens = await dropbox.refresh_dropbox_token(refresh_token_val)
                creds = {**creds, **new_tokens}
                access_token = new_tokens["access_token"]
                await db.integration.update(
                    where={"id": integration_id},
                    data={"encrypted_credentials": encrypt_credentials(creds, tenant_id)},
                )
        except Exception as exc:
            logger.error("dropbox_token_refresh_failed integration_id=%s: %s", integration_id, type(exc).__name__)

    initial_status = integration.status
    sync_start = time.monotonic()
    sync_status = "success"
    file_count = 0
    files: list = []

    try:
        files = await dropbox.list_pdf_files(access_token)
        file_count = len(files)
        logger.info("dropbox_pdf_files_found integration_id=%s count=%d", integration_id, file_count)
    except Exception as exc:
        logger.error("dropbox_sync_list_failed integration_id=%s: %s", integration_id, type(exc).__name__)
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
        logger.info("dropbox_sync_aborted_disconnected integration_id=%s", integration_id)
        return {"status": "skipped", "reason": "disconnected_during_sync"}

    if sync_status == "success":
        await db.integration.update(
            where={"id": integration_id},
            data={"status": "connected", "connected_at": datetime.now(UTC)},
        )
        if initial_status == "connected" and files:
            try:
                from app.orchestrator.events import enqueue_orchestrator_event
                for f in files:
                    file_id = f.get("id", "")
                    if not file_id:
                        continue
                    input_ref = f"dropbox:{file_id}"
                    # Idempotency: skip if an execution already exists for this file
                    existing = await db.execution.find_first(
                        where={"input_ref": input_ref, "tenant_id": tenant_id}
                    )
                    if existing:
                        continue
                    await enqueue_orchestrator_event(
                        tenant_id=tenant_id,
                        event_type="receipt_received",
                        payload={
                            "source": "dropbox",
                            "integration_id": integration_id,
                            "file_id": file_id,
                            "file_name": f.get("name", ""),
                        },
                        idempotency_key=input_ref,
                        db=db,
                    )
            except Exception as exc:
                logger.error(
                    "dropbox_receipt_event_failed integration_id=%s: %s",
                    integration_id, type(exc).__name__,
                )
        logger.info("dropbox_sync_ok tenant=%s files=%d", tenant_id, file_count)
        return {"status": "ok", "files_found": file_count}

    await db.integration.update(where={"id": integration_id}, data={"status": "error"})
    return {"status": "error", "reason": "sync_failed"}


async def enqueue_dropbox_sync(integration_id: str, tenant_id: str) -> None:
    """Enqueues a Dropbox sync job onto the arq Redis queue."""
    from app.queue.pool import get_queue_pool
    pool = await get_queue_pool()
    await pool.enqueue_job("sync_dropbox_connection", integration_id, tenant_id)
