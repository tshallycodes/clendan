"""
Google Drive sync job — runs via arq tool.
Lists PDF files in Drive, writes sync log, updates integration status.
"""
import base64
import time
import uuid
from datetime import datetime, UTC, timedelta

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.encryption import decrypt_credentials, encrypt_credentials
from app.integrations.google import client as google

logger = get_logger(__name__)

# Renew the Drive push channel this long before it expires, and how long each lasts.
_WATCH_TTL_SECONDS = 7 * 24 * 3600
_WATCH_RENEW_MARGIN = timedelta(hours=48)


async def _ensure_drive_watch(db, integration, access_token: str) -> None:
    """Register or renew the Drive push-notification channel so new files in the watch
    folder are detected in near-real-time. Best-effort - never raises; the daily poll is
    the fallback."""
    now = datetime.now(UTC)
    expires_at = getattr(integration, "webhook_expires_at", None)
    if expires_at and expires_at.replace(tzinfo=UTC) > now + _WATCH_RENEW_MARGIN:
        return  # channel still valid

    try:
        settings = get_settings()
        page_token = await google.get_changes_start_page_token(access_token)
        channel_id = str(uuid.uuid4())
        webhook_url = f"{settings.backend_base_url.rstrip('/')}/webhooks/google-drive"
        result = await google.watch_drive_changes(
            access_token,
            channel_id=channel_id,
            webhook_url=webhook_url,
            page_token=page_token,
            ttl_seconds=_WATCH_TTL_SECONDS,
        )
        exp_ms = result.get("expiration")
        new_expires = (
            datetime.fromtimestamp(int(exp_ms) / 1000, tz=UTC)
            if exp_ms else now + timedelta(seconds=_WATCH_TTL_SECONDS)
        )
        await db.integration.update(
            where={"id": integration.id},
            data={
                "webhook_channel_id": channel_id,
                "webhook_resource_id": result.get("resource_id", ""),
                "webhook_expires_at": new_expires,
            },
        )
        logger.info("drive_watch_registered integration_id=%s expires=%s", integration.id, new_expires.isoformat())
    except Exception as exc:
        logger.error("drive_watch_register_failed integration_id=%s: %s", integration.id, type(exc).__name__)


async def sync_drive_connection(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: list PDF files in Drive, write sync log, mark integration as connected.
    Returns sync result dict.
    """
    db = get_db()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration:
        logger.warning("drive_sync_skipped_not_found integration_id=%s", integration_id)
        return {"status": "skipped", "reason": "not_found"}

    if integration.tenant_id != tenant_id:
        logger.error("drive_sync_tenant_mismatch integration_id=%s", integration_id)
        return {"status": "error", "reason": "tenant_mismatch"}

    if integration.status not in ("syncing", "connected"):
        logger.warning(
            "drive_sync_skipped_bad_status integration_id=%s status=%s",
            integration_id, integration.status,
        )
        return {"status": "skipped", "reason": "unexpected_status"}

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    except ValueError as exc:
        logger.error("drive_sync_decrypt_failed integration_id=%s: %s", integration_id, type(exc).__name__)
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        return {"status": "error", "reason": "decrypt_failed"}

    access_token = creds.get("access_token", "")
    refresh_token_val = creds.get("refresh_token", "")

    # Refresh token if expired
    token_expiry_at = creds.get("token_expiry_at")
    if token_expiry_at:
        try:
            if datetime.fromisoformat(token_expiry_at) <= datetime.now(UTC):
                logger.info("drive_token_expired_refreshing integration_id=%s", integration_id)
                new_tokens = await google.refresh_google_token(refresh_token_val)
                creds = {**creds, **new_tokens}
                access_token = new_tokens["access_token"]
                await db.integration.update(
                    where={"id": integration_id},
                    data={"encrypted_credentials": encrypt_credentials(creds, tenant_id)},
                )
        except Exception as exc:
            logger.error("drive_token_refresh_failed integration_id=%s: %s", integration_id, type(exc).__name__)

    sync_start = time.monotonic()
    sync_status = "success"
    file_count = 0
    files: list = []

    # Privacy-safe scoping: only files inside the configured watch folder are ever read.
    # No folder configured (or the folder cannot be resolved) => process nothing. We never
    # sweep the whole drive.
    watch_folder = getattr(integration, "watch_folder", None)
    folder_id: str | None = None
    if watch_folder:
        try:
            folder_id = await google.find_folder_id_by_name(access_token, watch_folder)
        except Exception as exc:
            logger.error("drive_folder_resolve_failed integration_id=%s: %s", integration_id, type(exc).__name__)
        if not folder_id:
            logger.warning("drive_watch_folder_not_found integration_id=%s folder=%s", integration_id, watch_folder)

    if watch_folder and folder_id:
        try:
            files = await google.list_pdf_files(access_token, folder_id=folder_id)
            file_count = len(files)
            logger.info("drive_pdf_files_found integration_id=%s count=%d", integration_id, file_count)
        except Exception as exc:
            logger.error("drive_sync_failed integration_id=%s: %s", integration_id, type(exc).__name__)
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

    if sync_status == "success":
        from prisma import Json
        await db.integration.update(
            where={"id": integration_id},
            data={
                "status": "connected",
                "connected_at": datetime.now(UTC),
                "last_synced_at": datetime.now(UTC),
                "sync_metadata": Json({"files": file_count}),
            },
        )
        # Process every file in the watch folder (first sync included, so existing files
        # are backfilled). Dedup by execution input_ref keeps repeat syncs idempotent.
        if files:
            from app.events import enqueue_event
            _MAX_BYTES = 10 * 1024 * 1024
            for f in files:
                file_id = f.get("id", "")
                if not file_id:
                    continue
                idempotency_key = f"drive:document:{file_id}"
                existing = await db.execution.find_first(
                    where={"input_ref": idempotency_key, "tenant_id": tenant_id}
                )
                if existing:
                    continue
                try:
                    file_bytes = await google.download_drive_file_bytes(access_token, file_id)
                except Exception as exc:
                    logger.warning("drive_file_download_failed file_id=%s: %s", file_id, type(exc).__name__)
                    continue
                if len(file_bytes) > _MAX_BYTES:
                    logger.warning("drive_file_too_large file_id=%s size=%d", file_id, len(file_bytes))
                    continue
                try:
                    await enqueue_event(
                        tenant_id=tenant_id,
                        event_type="document_received",
                        payload={
                            "source": "google_drive",
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
                    logger.error("drive_document_event_failed file_id=%s: %s", file_id, type(exc).__name__)

        # Keep a live push channel so new uploads to the watch folder are detected in
        # near-real-time (renewed here whenever it is within the margin of expiry).
        if watch_folder:
            await _ensure_drive_watch(db, integration, access_token)

        logger.info("drive_sync_ok tenant=%s files=%d", tenant_id, file_count)
        return {"status": "ok", "files_found": file_count}

    await db.integration.update(where={"id": integration_id}, data={"status": "error"})
    return {"status": "error", "reason": "sync_failed"}


async def enqueue_drive_sync(integration_id: str, tenant_id: str) -> None:
    """Enqueues a Google Drive sync job onto the arq Redis queue."""
    import arq
    settings = get_settings()
    redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_public_url))
    await redis.enqueue_job("sync_drive_connection", integration_id, tenant_id)
    await redis.aclose()
