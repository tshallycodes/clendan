"""
Outlook sync job — runs via arq worker.
Creates Graph API mail subscription, scans messages with attachments,
downloads PDF attachments, enqueues each through the invoice worker.
"""
import time
from datetime import datetime, UTC

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.encryption import decrypt_credentials, encrypt_credentials
from app.integrations.outlook import client as outlook

logger = get_logger(__name__)


async def sync_outlook_connection(ctx: dict, integration_id: str, tenant_id: str) -> dict:
    """
    arq job: creates mail subscription, scans messages with attachments,
    downloads PDFs, enqueues invoice jobs, writes sync log, marks connected.
    Returns sync result dict.
    """
    db = get_db()
    settings = get_settings()

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration:
        logger.warning("outlook_sync_skipped_not_found integration_id=%s", integration_id)
        return {"status": "skipped", "reason": "not_found"}

    if integration.tenant_id != tenant_id:
        logger.error("outlook_sync_tenant_mismatch integration_id=%s", integration_id)
        return {"status": "error", "reason": "tenant_mismatch"}

    if integration.status not in ("syncing", "connected"):
        logger.warning(
            "outlook_sync_skipped_bad_status integration_id=%s status=%s",
            integration_id, integration.status,
        )
        return {"status": "skipped", "reason": "unexpected_status"}

    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    except ValueError as exc:
        logger.error("outlook_sync_decrypt_failed integration_id=%s: %s", integration_id, type(exc).__name__)
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        return {"status": "error", "reason": "decrypt_failed"}

    access_token = creds.get("access_token", "")
    if not access_token:
        logger.error("outlook_sync_no_access_token integration_id=%s", integration_id)
        await db.integration.update(where={"id": integration_id}, data={"status": "error"})
        return {"status": "error", "reason": "missing_access_token"}

    # Refresh token if expired
    token_expiry_at = creds.get("token_expiry_at")
    if token_expiry_at:
        try:
            if datetime.fromisoformat(token_expiry_at) <= datetime.now(UTC):
                logger.info("outlook_token_expired_refreshing integration_id=%s", integration_id)
                new_tokens = await outlook.refresh_outlook_token(creds.get("refresh_token", ""))
                creds = {**creds, **new_tokens}
                access_token = new_tokens["access_token"]
                await db.integration.update(
                    where={"id": integration_id},
                    data={"encrypted_credentials": encrypt_credentials(creds, tenant_id)},
                )
        except Exception as exc:
            logger.error("outlook_token_refresh_failed integration_id=%s: %s", integration_id, type(exc).__name__)

    # ---------------------------------------------------------------------------
    # Create mail subscription
    # ---------------------------------------------------------------------------
    notification_url = f"{settings.backend_base_url}/v1/webhooks/outlook"
    client_state = tenant_id

    subscription_id = creds.get("subscription_id", "")
    try:
        subscription = await outlook.create_mail_subscription(
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
        logger.info("outlook_subscription_created integration_id=%s subscription_id=%s", integration_id, subscription_id)
    except Exception as exc:
        logger.error(
            "outlook_subscription_create_failed integration_id=%s: %s",
            integration_id, type(exc).__name__,
        )

    # ---------------------------------------------------------------------------
    # Scan messages and process PDF attachments
    # ---------------------------------------------------------------------------
    start = time.monotonic()
    sync_status = "success"
    messages_count = 0
    pdf_count = 0

    try:
        messages = await outlook.list_messages_with_attachments(access_token=access_token)
        messages_count = len(messages)
        logger.info("outlook_sync_messages integration_id=%s count=%d", integration_id, messages_count)

        worker = await db.worker.find_first(
            where={"tenant_id": tenant_id, "type": "invoice_processing", "status": "active"}
        )

        for message in messages:
            message_id = message.get("id", "")
            if not message_id:
                continue
            try:
                attachments = await outlook.get_message_attachments(access_token, message_id)
                for attachment in attachments:
                    name = attachment.get("name", "")
                    content_type = attachment.get("contentType", "")
                    is_pdf = content_type == "application/pdf" or name.lower().endswith(".pdf")
                    if not is_pdf:
                        continue

                    try:
                        file_bytes = outlook.extract_attachment_bytes(attachment)
                    except ValueError as exc:
                        logger.warning("outlook_attachment_extract_failed message_id=%s: %s", message_id, exc)
                        continue

                    if not worker:
                        logger.info("outlook_no_invoice_worker tenant=%s — skipping PDF", tenant_id)
                        continue

                    input_ref = f"outlook:{message_id}:{attachment.get('id', name)}"
                    if await db.execution.find_first(where={"input_ref": input_ref}):
                        continue

                    execution = await db.execution.create(data={
                        "tenant_id": tenant_id,
                        "worker_id": worker.id,
                        "status": "queued",
                        "input_ref": input_ref,
                    })

                    await _enqueue_invoice_job(
                        execution_id=execution.id,
                        tenant_id=tenant_id,
                        worker_id=worker.id,
                        file_bytes=file_bytes,
                        content_type="application/pdf",
                        policy_config={},
                    )
                    pdf_count += 1
                    logger.info(
                        "outlook_invoice_queued execution_id=%s tenant=%s filename=%s",
                        execution.id, tenant_id, name,
                    )
            except Exception as exc:
                logger.warning("outlook_message_processing_failed message_id=%s: %s", message_id, type(exc).__name__)

    except Exception as exc:
        logger.error("outlook_sync_failed integration_id=%s: %s", integration_id, type(exc).__name__)
        sync_status = "error"

    elapsed_ms = int((time.monotonic() - start) * 1000)

    await db.integrationsynclog.create(data={
        "tenant_id": tenant_id,
        "integration_id": integration_id,
        "entity_type": "emails",
        "status": sync_status,
        "records_synced": messages_count,
        "duration_ms": elapsed_ms,
    })

    await db.integration.update(
        where={"id": integration_id},
        data={"status": "connected", "connected_at": datetime.now(UTC)},
    )

    logger.info(
        "outlook_sync_ok tenant=%s messages=%d pdfs_queued=%d elapsed_ms=%d",
        tenant_id, messages_count, pdf_count, elapsed_ms,
    )
    return {
        "status": "ok",
        "messages_with_attachments": messages_count,
        "pdf_invoices_queued": pdf_count,
        "subscription_id": subscription_id,
    }


async def renew_outlook_subscriptions(ctx: dict) -> None:
    """
    Renews all active Outlook subscriptions before they expire.
    Intended to run daily as a scheduled arq job.
    """
    db = get_db()

    integrations = await db.integration.find_many(
        where={"type": "outlook", "status": "connected"}
    )

    for integration in integrations:
        tenant_id = integration.tenant_id
        try:
            creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
        except ValueError:
            logger.error("outlook_renew_decrypt_failed integration_id=%s", integration.id)
            continue

        subscription_id = creds.get("subscription_id", "")
        access_token = creds.get("access_token", "")

        if not subscription_id or not access_token:
            logger.warning("outlook_renew_skipped_missing_fields integration_id=%s", integration.id)
            continue

        try:
            updated = await outlook.renew_subscription(
                access_token=access_token,
                subscription_id=subscription_id,
            )
            creds["subscription_expiry"] = updated.get("expirationDateTime", "")
            await db.integration.update(
                where={"id": integration.id},
                data={"encrypted_credentials": encrypt_credentials(creds, tenant_id)},
            )
            logger.info(
                "outlook_subscription_renewed integration_id=%s subscription_id=%s",
                integration.id, subscription_id,
            )
        except Exception as exc:
            logger.error(
                "outlook_subscription_renew_failed integration_id=%s: %s",
                integration.id, type(exc).__name__,
            )


async def _enqueue_invoice_job(
    *,
    execution_id: str,
    tenant_id: str,
    worker_id: str,
    file_bytes: bytes,
    content_type: str,
    policy_config: dict,
) -> None:
    """Enqueues run_invoice_job onto the arq Redis queue."""
    import arq
    settings = get_settings()
    redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_url))
    await redis.enqueue_job(
        "run_invoice_job",
        execution_id=execution_id,
        tenant_id=tenant_id,
        worker_id=worker_id,
        file_bytes=file_bytes,
        content_type=content_type,
        policy_config=policy_config,
    )
    await redis.aclose()


async def enqueue_outlook_sync(integration_id: str, tenant_id: str) -> None:
    """Enqueues sync_outlook_connection as an arq job onto the Redis queue."""
    import arq
    settings = get_settings()
    redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(settings.redis_url))
    await redis.enqueue_job("sync_outlook_connection", integration_id, tenant_id)
    await redis.aclose()
