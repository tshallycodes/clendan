"""
Gmail sync job — runs via arq tool.
Sets up Gmail watch, scans the last 30 days of emails with attachments,
downloads PDF attachments, and enqueues each one through the invoice worker.
"""
import time
from datetime import datetime, UTC, timedelta

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.encryption import decrypt_credentials, encrypt_credentials
from app.integrations.google import client as google

logger = get_logger(__name__)


async def sync_gmail_connection(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: set up Gmail watch, scan last 30 days of emails with attachments,
    write sync log, and mark integration as connected.
    Returns sync result dict.
    """
    db = get_db()
    settings = get_settings()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration:
        logger.warning("gmail_sync_skipped_not_found integration_id=%s", integration_id)
        return {"status": "skipped", "reason": "not_found"}

    if integration.tenant_id != tenant_id:
        logger.error("gmail_sync_tenant_mismatch integration_id=%s", integration_id)
        return {"status": "error", "reason": "tenant_mismatch"}

    if integration.status not in ("syncing", "connected"):
        logger.warning(
            "gmail_sync_skipped_bad_status integration_id=%s status=%s",
            integration_id, integration.status,
        )
        return {"status": "skipped", "reason": "unexpected_status"}

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    except ValueError as exc:
        logger.error("gmail_sync_decrypt_failed integration_id=%s: %s", integration_id, type(exc).__name__)
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        return {"status": "error", "reason": "decrypt_failed"}

    access_token = creds.get("access_token", "")
    refresh_token_val = creds.get("refresh_token", "")

    # Refresh token if expired
    token_expiry_at = creds.get("token_expiry_at")
    if token_expiry_at:
        try:
            if datetime.fromisoformat(token_expiry_at) <= datetime.now(UTC):
                logger.info("gmail_token_expired_refreshing integration_id=%s", integration_id)
                new_tokens = await google.refresh_google_token(refresh_token_val)
                creds = {**creds, **new_tokens}
                access_token = new_tokens["access_token"]
                await db.integration.update(
                    where={"id": integration_id},
                    data={"encrypted_credentials": encrypt_credentials(creds, tenant_id)},
                )
        except Exception as exc:
            logger.error("gmail_token_refresh_failed integration_id=%s: %s", integration_id, type(exc).__name__)

    initial_status = integration.status
    sync_start = time.monotonic()
    sync_status = "success"
    message_count = 0
    pdf_count = 0
    pdf_attachments: list[tuple[str, str, str]] = []  # (message_id, attachment_id, filename)

    try:
        # Set up Gmail watch if pubsub topic is configured
        watch_result: dict = {}
        if settings.google_pubsub_topic:
            try:
                watch_result = await google.setup_gmail_watch(access_token, settings.google_pubsub_topic)
                logger.info(
                    "gmail_watch_setup integration_id=%s history_id=%s",
                    integration_id, watch_result.get("historyId"),
                )
            except Exception as exc:
                logger.warning(
                    "gmail_watch_setup_failed integration_id=%s: %s",
                    integration_id, type(exc).__name__,
                )

        # Scan last 30 days for emails with attachments
        thirty_days_ago = (datetime.now(UTC) - timedelta(days=30)).strftime("%Y/%m/%d")
        messages = await google.list_messages_with_attachments(access_token, thirty_days_ago)
        message_count = len(messages)
        logger.info("gmail_messages_found integration_id=%s count=%d", integration_id, message_count)

        # Download PDF attachments and enqueue each through the invoice worker
        for stub in messages:
            try:
                msg = await google.get_message_parts(access_token, stub["id"])
                parts = _flatten_parts((msg.get("payload") or {}).get("parts") or [])
                for part in parts:
                    mime = part.get("mimeType", "")
                    filename = part.get("filename", "")
                    if mime == "application/pdf" or filename.lower().endswith(".pdf"):
                        pdf_count += 1
                        attachment_id = (part.get("body") or {}).get("attachmentId", "")
                        if attachment_id:
                            pdf_attachments.append((stub["id"], attachment_id, filename))
            except Exception as exc:
                logger.warning(
                    "gmail_message_processing_failed message_id=%s: %s",
                    stub.get("id"), type(exc).__name__,
                )

        # Persist watch metadata back into credentials
        updated_creds = {**creds}
        if watch_result:
            updated_creds["history_id"] = watch_result.get("historyId", "")
            updated_creds["watch_expiry"] = watch_result.get("expiration", "")
        await db.integration.update(
            where={"id": integration_id},
            data={"encrypted_credentials": encrypt_credentials(updated_creds, tenant_id)},
        )

    except Exception as exc:
        logger.error("gmail_sync_failed integration_id=%s: %s", integration_id, type(exc).__name__)
        sync_status = "error"

    elapsed_ms = int((time.monotonic() - sync_start) * 1000)

    await db.integrationsynclog.create(data={
        "tenant_id": tenant_id,
        "integration_id": integration_id,
        "entity_type": "emails",
        "status": sync_status,
        "records_synced": message_count,
        "duration_ms": elapsed_ms,
    })

    if sync_status == "success":
        await db.integration.update(
            where={"id": integration_id},
            data={"status": "connected", "connected_at": datetime.now(UTC)},
        )
        if initial_status == "connected" and pdf_attachments:
            try:
                from app.events import enqueue_event
                for message_id, attachment_id, att_filename in pdf_attachments:
                    name_lower = att_filename.lower()
                    _doc_type = (
                        "receipt" if "receipt" in name_lower else
                        "contract" if "contract" in name_lower or "agreement" in name_lower else
                        "invoice"
                    )
                    await enqueue_event(
                        tenant_id=tenant_id,
                        event_type="receipt_received",
                        payload={
                            "source": "gmail",
                            "integration_id": integration_id,
                            "message_id": message_id,
                            "attachment_id": attachment_id,
                        },
                        idempotency_key=f"gmail:receipt:{message_id}:{attachment_id}",
                        db=db,
                    )
                    await enqueue_event(
                        tenant_id=tenant_id,
                        event_type="document_received",
                        payload={
                            "source": "gmail",
                            "integration_id": integration_id,
                            "message_id": message_id,
                            "attachment_id": attachment_id,
                            "document_type": _doc_type,
                            "filename": att_filename,
                        },
                        idempotency_key=f"gmail:document:{message_id}:{attachment_id}",
                        db=db,
                    )
            except Exception as exc:
                logger.error(
                    "gmail_document_event_failed integration_id=%s: %s",
                    integration_id, type(exc).__name__,
                )
        logger.info(
            "gmail_sync_ok tenant=%s messages=%d pdfs=%d",
            tenant_id, message_count, pdf_count,
        )
        return {"status": "ok", "messages_scanned": message_count, "pdf_attachments_found": pdf_count}

    await db.integration.update(where={"id": integration_id}, data={"status": "error"})
    return {"status": "error", "reason": "sync_failed"}


def _flatten_parts(parts: list) -> list:
    """Recursively flattens nested MIME parts (multipart/* containers)."""
    result = []
    for part in parts:
        result.append(part)
        result.extend(_flatten_parts(part.get("parts") or []))
    return result


async def enqueue_gmail_sync(integration_id: str, tenant_id: str) -> None:
    """Enqueues a Gmail sync job onto the arq Redis queue."""
    import arq
    settings = get_settings()
    redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_public_url))
    await redis.enqueue_job("sync_gmail_connection", integration_id, tenant_id)
    await redis.aclose()
