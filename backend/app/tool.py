"""
arq tool process — runs background jobs via Redis.
Start with: python -m arq app.tool.ToolSettings
"""
import time
from datetime import UTC, datetime

from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.db import connect_db, disconnect_db, get_db
from app.core.execution import complete_execution
from app.core.logging import get_logger
from app.integrations.plaid.sync import reconcile_plaid_transactions, sync_plaid_transactions
from app.integrations.quickbooks.sync import sync_quickbooks_connection
from app.integrations.xero.sync import sync_xero_connection
from app.integrations.freshbooks.sync import sync_freshbooks_connection
from app.integrations.stripe.sync import sync_stripe_connection
from app.integrations.gocardless.sync import sync_gocardless_connection
from app.integrations.square.sync import sync_square_connection
from app.integrations.paypal.sync import sync_paypal_connection
from app.integrations.truelayer.sync import sync_truelayer_connection
from app.integrations.mono.sync import sync_mono_transactions, reconcile_mono_transactions
from app.integrations.codat.sync import sync_codat_connection
from app.integrations.codat.sync import poll_codat_status
from app.integrations.google.sync_gmail import sync_gmail_connection
from app.integrations.google.sync_drive import sync_drive_connection
from app.integrations.dropbox.sync import sync_dropbox_connection
from app.integrations.outlook.sync import sync_outlook_connection
from app.integrations.outlook.sync import renew_outlook_subscriptions
from app.integrations.sage.sync import sync_sage_connection
from app.integrations.adyen.sync import sync_adyen_connection
from app.integrations.wise.sync import sync_wise_connection
from app.integrations.sap.sync import sync_sap_connection
from app.integrations.netsuite.sync import sync_netsuite_connection
from app.integrations.dynamics.sync import sync_dynamics_connection
from app.integrations.onedrive.sync import sync_onedrive_connection
from app.integrations.exchange_rates.service import fetch_exchange_rates_daily
from app.queue.pool import get_queue_pool
from app.tools.invoice_processing import run_invoice_job
from app.tools.receipt_processing import run_receipt_job
from app.api.v1.parse.invoice import run_parse_invoice_job
from app.api.v1.parse.receipt import run_parse_receipt_job
from app.tools.reconciliation import run_reconciliation_job
from app.tools.spend_control import run_expense_control_job, run_accounts_payable_job
from app.tools.tax_compliance import run_tax_compliance_job
from app.tools.financial_reporting import run_financial_reporting_job
from app.tools.payment_run import run_payment_run_job
from app.tools.accounts_receivable import run_ar_collections_job
from app.tools.document_intelligence import run_document_intelligence_job
from app.tools.month_end_close import run_month_end_close_job, run_month_end_close_scheduled
from app.tools.payroll_reconciliation import run_payroll_rec_job
from app.tools.journal_entries import run_journal_entry_job

logger = get_logger(__name__)

_DAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}




async def run_invoice_received_job(
    _ctx: dict,
    *,
    execution_id: str,
    tenant_id: str,
    tool_id: str,
    payload: dict,
) -> dict:
    """arq job: fetches a QB Invoice/Bill from a webhook event, applies policy, stores it."""
    from app.policy.engine import evaluate_policy
    db = get_db()
    start_ms = int(time.time() * 1000)

    await db.execution.update(where={"id": execution_id}, data={"status": "running"})

    try:
        qb_entity = payload.get("qb_entity", "Invoice")
        qb_entity_id = payload.get("qb_entity_id", "")
        realm_id = payload.get("realm_id", "")
        integration_id = payload.get("integration_id", "")

        if not all([qb_entity_id, realm_id, integration_id]):
            await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                tenant_id=tenant_id, decision="blocked", confidence=0.0,
                duration_ms=int(time.time() * 1000) - start_ms)
            return {"decision": "blocked", "reason": "Missing required QB invoice payload fields"}

        integration = await db.integration.find_unique(where={"id": integration_id})
        if not integration or integration.status != "connected":
            await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                tenant_id=tenant_id, decision="blocked", confidence=0.0,
                duration_ms=int(time.time() * 1000) - start_ms)
            return {"decision": "blocked", "reason": "QuickBooks integration not connected"}

        try:
            from app.integrations.quickbooks import client as qb
            from app.integrations.encryption import decrypt_credentials as _dc
            settings = get_settings()
            creds = _dc(integration.encrypted_credentials, tenant_id)
            if qb_entity == "Invoice":
                entity_data = await qb.get_invoice(
                    encrypted_access=creds["access_token"], realm_id=realm_id,
                    invoice_id=qb_entity_id, sandbox=settings.quickbooks_sandbox,
                )
            else:
                entity_data = await qb.get_bill(
                    encrypted_access=creds["access_token"], realm_id=realm_id,
                    bill_id=qb_entity_id, sandbox=settings.quickbooks_sandbox,
                )
        except Exception as exc:
            await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                tenant_id=tenant_id, decision="blocked", confidence=0.0,
                duration_ms=int(time.time() * 1000) - start_ms)
            return {"decision": "blocked", "reason": f"QB fetch failed: {type(exc).__name__}"}

        if not entity_data:
            await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                tenant_id=tenant_id, decision="blocked", confidence=0.0,
                duration_ms=int(time.time() * 1000) - start_ms)
            return {"decision": "blocked", "reason": "QB returned empty entity"}

        tool = await db.tool.find_unique(where={"id": tool_id})
        policy_config = tool.config_json.get("policy", {}) if tool and isinstance(tool.config_json, dict) else {}

        policy_result = evaluate_policy(
            amount_minor=entity_data.get("amount_minor", 0),
            currency=entity_data.get("currency", "GBP"),
            vendor=entity_data.get("vendor", "unknown"),
            verified_suppliers=policy_config.get("verified_suppliers", []),
            allowed_currencies=policy_config.get("allowed_currencies", ["GBP", "USD", "EUR"]),
            auto_threshold_minor=policy_config.get("auto_threshold", 50000),
            block_threshold_minor=policy_config.get("approve_threshold", 500000),
        )

        invoice_number = entity_data.get("invoice_number", qb_entity_id)
        existing = await db.invoice.find_first(where={"tenant_id": tenant_id, "invoice_number": invoice_number})
        if not existing:
            due_date_str = entity_data.get("due_date")
            due_date = datetime.fromisoformat(due_date_str) if due_date_str else None
            await db.invoice.create(data={
                "tenant_id": tenant_id,
                "vendor": entity_data.get("vendor", "unknown"),
                "invoice_number": invoice_number,
                "amount_minor": entity_data.get("amount_minor", 0),
                "currency": entity_data.get("currency", "GBP"),
                "due_date": due_date,
                "status": policy_result.decision.value,
            })

        decision = policy_result.decision.value
        duration_ms = int(time.time() * 1000) - start_ms
        await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
            tenant_id=tenant_id, decision=decision, confidence=0.95, duration_ms=duration_ms)
        return {"decision": decision, "confidence": 0.95}

    except Exception as exc:
        logger.error("invoice_received_job_failed", extra={"execution_id": execution_id, "error": str(exc)})
        try:
            await db.execution.update(where={"id": execution_id},
                data={"status": "failed", "decision": "failed"})
        except Exception:
            pass
        raise


async def run_receipt_received_job(
    _ctx: dict,
    *,
    execution_id: str,
    tenant_id: str,
    tool_id: str,
    payload: dict,
) -> dict:
    """arq job: fetches receipt bytes from source integration and enqueues run_receipt_job."""
    db = get_db()
    start_ms = int(time.time() * 1000)

    await db.execution.update(where={"id": execution_id}, data={"status": "running"})

    try:
        source = payload.get("source", "")
        integration_id = payload.get("integration_id", "")

        if not source or not integration_id:
            await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                tenant_id=tenant_id, decision="blocked", confidence=0.0,
                duration_ms=int(time.time() * 1000) - start_ms)
            return {"decision": "blocked", "reason": "Missing source or integration_id in receipt payload"}

        integration = await db.integration.find_unique(where={"id": integration_id})
        if not integration or integration.status != "connected":
            await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                tenant_id=tenant_id, decision="blocked", confidence=0.0,
                duration_ms=int(time.time() * 1000) - start_ms)
            return {"decision": "blocked", "reason": "Source integration not connected"}
        if integration.tenant_id != tenant_id:
            await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                tenant_id=tenant_id, decision="blocked", confidence=0.0,
                duration_ms=int(time.time() * 1000) - start_ms)
            return {"decision": "blocked", "reason": "Tenant mismatch on receipt source integration"}

        from app.integrations.encryption import decrypt_credentials
        try:
            creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
        except Exception:
            await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                tenant_id=tenant_id, decision="blocked", confidence=0.0,
                duration_ms=int(time.time() * 1000) - start_ms)
            return {"decision": "blocked", "reason": "Failed to decrypt integration credentials"}

        access_token = creds.get("access_token", "")
        if not access_token:
            await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                tenant_id=tenant_id, decision="blocked", confidence=0.0,
                duration_ms=int(time.time() * 1000) - start_ms)
            return {"decision": "blocked", "reason": "No access token in integration credentials"}

        file_bytes: bytes = b""
        content_type = "application/pdf"

        try:
            if source == "gmail":
                from app.integrations.google import client as google
                message_id = payload.get("message_id", "")
                attachment_id = payload.get("attachment_id", "")
                if not message_id or not attachment_id:
                    await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                        tenant_id=tenant_id, decision="blocked", confidence=0.0,
                        duration_ms=int(time.time() * 1000) - start_ms)
                    return {"decision": "blocked", "reason": "Missing message_id or attachment_id for Gmail receipt"}
                file_bytes = await google.get_gmail_attachment_bytes(access_token, message_id, attachment_id)
            elif source == "google_drive":
                from app.integrations.google import client as google
                file_id = payload.get("file_id", "")
                if not file_id:
                    await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                        tenant_id=tenant_id, decision="blocked", confidence=0.0,
                        duration_ms=int(time.time() * 1000) - start_ms)
                    return {"decision": "blocked", "reason": "Missing file_id for Drive receipt"}
                file_bytes = await google.download_drive_file_bytes(access_token, file_id)
            elif source == "outlook":
                from app.integrations.outlook import client as outlook_client
                message_id = payload.get("message_id", "")
                if not message_id:
                    await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                        tenant_id=tenant_id, decision="blocked", confidence=0.0,
                        duration_ms=int(time.time() * 1000) - start_ms)
                    return {"decision": "blocked", "reason": "Missing message_id for Outlook receipt"}
                attachments = await outlook_client.get_message_attachments(access_token, message_id)
                pdf_attachment = next(
                    (a for a in attachments if "pdf" in a.get("contentType", "").lower()
                     or a.get("name", "").lower().endswith(".pdf")), None)
                if not pdf_attachment:
                    await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                        tenant_id=tenant_id, decision="blocked", confidence=0.0,
                        duration_ms=int(time.time() * 1000) - start_ms)
                    return {"decision": "blocked", "reason": "No PDF attachment found in Outlook message"}
                file_bytes, content_type = await outlook_client.get_attachment_bytes(
                    access_token, message_id, pdf_attachment["id"])
            elif source == "onedrive":
                from app.integrations.onedrive import client as onedrive_client
                file_id = payload.get("file_id", "")
                if not file_id:
                    await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                        tenant_id=tenant_id, decision="blocked", confidence=0.0,
                        duration_ms=int(time.time() * 1000) - start_ms)
                    return {"decision": "blocked", "reason": "Missing file_id for OneDrive receipt"}
                file_bytes = await onedrive_client.download_file(access_token, file_id)
            else:
                await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                    tenant_id=tenant_id, decision="blocked", confidence=0.0,
                    duration_ms=int(time.time() * 1000) - start_ms)
                return {"decision": "blocked", "reason": f"Unknown receipt source: {source}"}
        except Exception as exc:
            await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                tenant_id=tenant_id, decision="blocked", confidence=0.0,
                duration_ms=int(time.time() * 1000) - start_ms)
            return {"decision": "blocked", "reason": f"Failed to fetch receipt from {source}: {type(exc).__name__}"}

        if not file_bytes:
            await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                tenant_id=tenant_id, decision="blocked", confidence=0.0,
                duration_ms=int(time.time() * 1000) - start_ms)
            return {"decision": "blocked", "reason": "Empty receipt file returned from source"}

        tool = await db.tool.find_unique(where={"id": tool_id})
        policy_config = tool.config_json.get("policy", {}) if tool and isinstance(tool.config_json, dict) else {}

        pool = await get_queue_pool()
        await pool.enqueue_job(
            "run_receipt_job",
            execution_id=execution_id, tenant_id=tenant_id, tool_id=tool_id,
            file_bytes=file_bytes, content_type=content_type, policy_config=policy_config,
        )
        return {"decision": "routed"}

    except Exception as exc:
        logger.error("receipt_received_job_failed", extra={"execution_id": execution_id, "error": str(exc)})
        try:
            await db.execution.update(where={"id": execution_id}, data={"status": "failed", "decision": "failed"})
        except Exception:
            pass
        raise


async def run_document_received_job(
    _ctx: dict,
    *,
    execution_id: str,
    tenant_id: str,
    tool_id: str,
    payload: dict,
) -> dict:
    """arq job: fetches document bytes from source integration, creates Document record, enqueues run_document_intelligence_job."""
    from app.tools.document_intelligence import _ALLOWED_CONTENT_TYPES, _generate_thumbnail
    db = get_db()
    start_ms = int(time.time() * 1000)

    await db.execution.update(where={"id": execution_id}, data={"status": "running"})

    try:
        source = payload.get("source", "")
        integration_id = payload.get("integration_id", "")
        document_type = payload.get("document_type", "invoice")
        filename = payload.get("filename")

        if not source or not integration_id:
            await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                tenant_id=tenant_id, decision="blocked", confidence=0.0,
                duration_ms=int(time.time() * 1000) - start_ms)
            return {"decision": "blocked", "reason": "Missing source or integration_id in document payload"}

        integration = await db.integration.find_unique(where={"id": integration_id})
        if not integration or integration.status != "connected":
            await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                tenant_id=tenant_id, decision="blocked", confidence=0.0,
                duration_ms=int(time.time() * 1000) - start_ms)
            return {"decision": "blocked", "reason": "Source integration not connected"}
        if integration.tenant_id != tenant_id:
            await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                tenant_id=tenant_id, decision="blocked", confidence=0.0,
                duration_ms=int(time.time() * 1000) - start_ms)
            return {"decision": "blocked", "reason": "Tenant mismatch on document source integration"}

        from app.integrations.encryption import decrypt_credentials
        try:
            creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
        except Exception:
            await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                tenant_id=tenant_id, decision="blocked", confidence=0.0,
                duration_ms=int(time.time() * 1000) - start_ms)
            return {"decision": "blocked", "reason": "Failed to decrypt integration credentials"}

        access_token = creds.get("access_token", "")
        if not access_token:
            await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                tenant_id=tenant_id, decision="blocked", confidence=0.0,
                duration_ms=int(time.time() * 1000) - start_ms)
            return {"decision": "blocked", "reason": "No access token in integration credentials"}

        file_bytes: bytes = b""
        content_type = "application/pdf"

        try:
            if source == "gmail":
                from app.integrations.google import client as google
                message_id = payload.get("message_id", "")
                attachment_id = payload.get("attachment_id", "")
                if not message_id or not attachment_id:
                    await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                        tenant_id=tenant_id, decision="blocked", confidence=0.0,
                        duration_ms=int(time.time() * 1000) - start_ms)
                    return {"decision": "blocked", "reason": "Missing message_id or attachment_id for Gmail document"}
                file_bytes = await google.get_gmail_attachment_bytes(access_token, message_id, attachment_id)
            elif source == "google_drive":
                from app.integrations.google import client as google
                file_id = payload.get("file_id", "")
                if not file_id:
                    await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                        tenant_id=tenant_id, decision="blocked", confidence=0.0,
                        duration_ms=int(time.time() * 1000) - start_ms)
                    return {"decision": "blocked", "reason": "Missing file_id for Drive document"}
                file_bytes = await google.download_drive_file_bytes(access_token, file_id)
            elif source == "outlook":
                from app.integrations.outlook import client as outlook_client
                message_id = payload.get("message_id", "")
                if not message_id:
                    await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                        tenant_id=tenant_id, decision="blocked", confidence=0.0,
                        duration_ms=int(time.time() * 1000) - start_ms)
                    return {"decision": "blocked", "reason": "Missing message_id for Outlook document"}
                attachments = await outlook_client.get_message_attachments(access_token, message_id)
                pdf_attachment = next(
                    (a for a in attachments if "pdf" in a.get("contentType", "").lower()
                     or a.get("name", "").lower().endswith(".pdf")), None)
                if not pdf_attachment:
                    await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                        tenant_id=tenant_id, decision="blocked", confidence=0.0,
                        duration_ms=int(time.time() * 1000) - start_ms)
                    return {"decision": "blocked", "reason": "No PDF attachment found in Outlook message"}
                file_bytes, content_type = await outlook_client.get_attachment_bytes(
                    access_token, message_id, pdf_attachment["id"])
                if not filename:
                    filename = pdf_attachment.get("name")
            elif source == "onedrive":
                from app.integrations.onedrive import client as onedrive_client
                file_id = payload.get("file_id", "")
                if not file_id:
                    await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                        tenant_id=tenant_id, decision="blocked", confidence=0.0,
                        duration_ms=int(time.time() * 1000) - start_ms)
                    return {"decision": "blocked", "reason": "Missing file_id for OneDrive document"}
                file_bytes = await onedrive_client.download_file(access_token, file_id)
            else:
                await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                    tenant_id=tenant_id, decision="blocked", confidence=0.0,
                    duration_ms=int(time.time() * 1000) - start_ms)
                return {"decision": "blocked", "reason": f"Unknown document source: {source}"}
        except Exception as exc:
            await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                tenant_id=tenant_id, decision="blocked", confidence=0.0,
                duration_ms=int(time.time() * 1000) - start_ms)
            return {"decision": "blocked", "reason": f"Failed to fetch document from {source}: {type(exc).__name__}"}

        if not file_bytes:
            await complete_execution(db=db, execution_id=execution_id, tool_id=tool_id,
                tenant_id=tenant_id, decision="blocked", confidence=0.0,
                duration_ms=int(time.time() * 1000) - start_ms)
            return {"decision": "blocked", "reason": "Empty document file returned from source"}

        if content_type not in _ALLOWED_CONTENT_TYPES:
            content_type = "application/pdf"

        tool = await db.tool.find_unique(where={"id": tool_id})
        policy_config = tool.config_json if tool and isinstance(tool.config_json, dict) else {}

        thumbnail_b64 = _generate_thumbnail(file_bytes, content_type)
        doc_record = await db.document.create(data={
            "tenant_id": tenant_id, "tool_id": tool_id, "execution_id": execution_id,
            "document_type": document_type, "filename": filename, "content_type": content_type,
            "file_size_bytes": len(file_bytes), "status": "processing", "thumbnail_b64": thumbnail_b64,
        })

        pool = await get_queue_pool()
        await pool.enqueue_job(
            "run_document_intelligence_job",
            execution_id=execution_id, tenant_id=tenant_id, tool_id=tool_id,
            file_bytes=file_bytes, content_type=content_type,
            policy_config=policy_config, document_id=doc_record.id,
        )
        return {"decision": "routed"}

    except Exception as exc:
        logger.error("document_received_job_failed", extra={"execution_id": execution_id, "error": str(exc)})
        try:
            await db.execution.update(where={"id": execution_id}, data={"status": "failed", "decision": "failed"})
        except Exception:
            pass
        raise


def _tenant_local_now(tenant, now_utc: datetime):
    """Convert UTC now to the tenant's configured timezone, falling back to UTC."""
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    tz_name = (tenant.timezone if tenant and tenant.timezone else None) or "UTC"
    try:
        return now_utc.astimezone(ZoneInfo(tz_name)), tz_name
    except ZoneInfoNotFoundError:
        return now_utc.astimezone(UTC), "UTC"


async def run_financial_reporting_monthly(_ctx: dict) -> None:
    """Hourly cron: fires financial_report_run on each tool's configured day-of-month + hour
    (in the tenant's timezone). Month-bucketed idempotency prevents double-firing."""
    from app.events import enqueue_event
    db = get_db()
    now_utc = datetime.now(UTC)
    tools = await db.tool.find_many(where={"type": "financial_reporting", "status": "active"})
    for tool in tools:
        try:
            cfg = tool.config_json or {}
            tenant = await db.tenant.find_unique(where={"id": tool.tenant_id})
            now_local, tz_name = _tenant_local_now(tenant, now_utc)
            if now_local.hour != int(cfg.get("run_hour", 1)):
                continue
            try:
                run_day = int(cfg.get("run_day_of_month", 1))
            except (TypeError, ValueError):
                run_day = 1
            run_day = max(1, min(run_day, 28))  # clamp to a day every month has
            if now_local.day != run_day:
                continue
            await enqueue_event(
                tenant_id=tool.tenant_id,
                event_type="financial_report_run",
                payload={},
                idempotency_key=f"financial_reporting:monthly:{tool.id}:{now_local.strftime('%Y-%m')}",
                db=db,
            )
            logger.info("financial_reporting_scheduled_fired tenant=%s tool=%s tz=%s", tool.tenant_id, tool.id, tz_name)
        except Exception as exc:
            logger.error("financial_reporting_cron_failed tenant=%s: %s", tool.tenant_id, type(exc).__name__)


async def run_payment_run_weekly(_ctx: dict) -> None:
    """Hourly cron: fires payment_run_requested on each tool's configured weekday + hour
    (in the tenant's timezone). Date-bucketed idempotency prevents double-firing."""
    from app.events import enqueue_event
    db = get_db()
    now_utc = datetime.now(UTC)
    tools = await db.tool.find_many(where={"type": "payment_run", "status": "active"})
    for tool in tools:
        try:
            cfg = tool.config_json or {}
            tenant = await db.tenant.find_unique(where={"id": tool.tenant_id})
            now_local, tz_name = _tenant_local_now(tenant, now_utc)
            if now_local.hour != int(cfg.get("run_hour", 7)):
                continue
            run_day = _DAY_MAP.get(str(cfg.get("run_day_of_week", "monday")).lower(), 0)
            if now_local.weekday() != run_day:
                continue
            await enqueue_event(
                tenant_id=tool.tenant_id,
                event_type="payment_run_requested",
                payload={},
                idempotency_key=f"payment_run:weekly:{tool.id}:{now_local.strftime('%Y-%m-%d')}",
                db=db,
            )
            logger.info("payment_run_scheduled_fired tenant=%s tool=%s tz=%s", tool.tenant_id, tool.id, tz_name)
        except Exception as exc:
            logger.error("payment_run_cron_failed tenant=%s: %s", tool.tenant_id, type(exc).__name__)


# integration type -> arq sync job name. Every job shares the (ctx, integration_id,
# tenant_id) signature the daily resync enqueues with. Document + email sources are
# included so Document Intelligence picks up newly-added files on the daily poll (each
# source sync dedups already-processed files, so re-scanning is safe).
_INTEGRATION_SYNC_JOBS: dict[str, str] = {
    # Accounting
    "quickbooks":   "sync_quickbooks_connection",
    "xero":         "sync_xero_connection",
    "freshbooks":   "sync_freshbooks_connection",
    "sage":         "sync_sage_connection",
    "netsuite":     "sync_netsuite_connection",
    "dynamics":     "sync_dynamics_connection",
    "sap":          "sync_sap_connection",
    "codat":        "sync_codat_connection",
    # Payment
    "stripe":       "sync_stripe_connection",
    "gocardless":   "sync_gocardless_connection",
    "square":       "sync_square_connection",
    "paypal":       "sync_paypal_connection",
    "adyen":        "sync_adyen_connection",
    "wise":         "sync_wise_connection",
    # Banking
    "plaid":        "sync_plaid_transactions",
    "truelayer":    "sync_truelayer_connection",
    "mono":         "sync_mono_transactions",
    # Document sources (feed Document Intelligence)
    "google_drive": "sync_drive_connection",
    "dropbox":      "sync_dropbox_connection",
    "onedrive":     "sync_onedrive_connection",
    # Email (invoice/receipt attachments feed Document Intelligence)
    "gmail":        "sync_gmail_connection",
    "outlook":      "sync_outlook_connection",
}


async def resync_integrations_daily(_ctx: dict) -> None:
    """Daily cron: re-enqueues sync jobs for every connected integration - accounting,
    payment, banking, document, and email sources - so new data and files are picked up."""
    db = get_db()
    pool = await get_queue_pool()
    day_key = datetime.now(UTC).strftime("%Y-%m-%d")

    integrations = await db.integration.find_many(
        where={
            "type": {"in": list(_INTEGRATION_SYNC_JOBS.keys())},
            "status": "connected",
        }
    )

    for intg in integrations:
        job_fn = _INTEGRATION_SYNC_JOBS.get(intg.type)
        if not job_fn:
            continue
        job_id = f"daily_resync:{intg.type}:{intg.id}:{day_key}"
        try:
            await pool.enqueue_job(
                job_fn,
                integration_id=intg.id,
                tenant_id=intg.tenant_id,
                _job_id=job_id,
            )
            logger.info(
                "daily_resync_enqueued type=%s integration_id=%s tenant_id=%s",
                intg.type, intg.id, intg.tenant_id,
            )
        except Exception as exc:
            logger.error(
                "daily_resync_enqueue_failed type=%s integration_id=%s: %s",
                intg.type, intg.id, type(exc).__name__,
            )


async def expire_stale_approvals(_ctx: dict) -> None:
    """Hourly cron: auto-reject approvals whose TTL has elapsed.

    A pending approval that is never actioned before ``expires_at`` is treated as a
    rejection: the decision cascades to the execution, source document, and any linked
    journal entry exactly as a human reject would, and the action is audited. This clears
    stale entries out of the Pending queue instead of leaving them un-actionable forever.
    """
    from app.core.approvals import resolve_approval

    db = get_db()
    now = datetime.now(UTC)
    stale = await db.approval.find_many(
        where={"status": "pending", "expires_at": {"lt": now}},
        take=500,
    )
    for approval in stale:
        try:
            await resolve_approval(
                db=db,
                approval=approval,
                action="reject",
                actor="system:approval_expiry",
            )
            logger.info(
                "approval_auto_rejected_expired approval_id=%s tenant_id=%s",
                approval.id, approval.tenant_id,
            )
        except Exception as exc:
            logger.error(
                "approval_expiry_failed approval_id=%s: %s",
                approval.id, type(exc).__name__,
            )


async def run_ar_collections_scheduled(_ctx: dict) -> None:
    """Daily cron: run AR collections for every active ar_collections tool so overdue
    customer invoices are aged and chased automatically. Date-bucketed idempotency key
    prevents double-firing within a day."""
    from app.events import enqueue_event
    db = get_db()
    day_key = datetime.now(UTC).strftime("%Y-%m-%d")
    tools = await db.tool.find_many(where={"type": "ar_collections", "status": "active"})
    for tool in tools:
        try:
            await enqueue_event(
                tenant_id=tool.tenant_id,
                event_type="ar_collections_run",
                payload={"source": "schedule"},
                idempotency_key=f"ar_collections:{tool.tenant_id}:{day_key}",
                db=db,
            )
        except Exception as exc:
            logger.error(
                "ar_collections_schedule_failed tenant=%s: %s",
                tool.tenant_id, type(exc).__name__,
            )


async def run_tax_compliance_scheduled(_ctx: dict) -> None:
    """Hourly cron: fires tax_compliance_run on each tool's configured day-of-month + hour
    (in the tenant's timezone), so the VAT position is recomputed and the return recorded on
    a schedule. Month-bucketed idempotency prevents double-firing."""
    from app.events import enqueue_event
    db = get_db()
    now_utc = datetime.now(UTC)
    tools = await db.tool.find_many(where={"type": "tax_compliance", "status": "active"})
    for tool in tools:
        try:
            cfg = tool.config_json or {}
            tenant = await db.tenant.find_unique(where={"id": tool.tenant_id})
            now_local, tz_name = _tenant_local_now(tenant, now_utc)
            if now_local.hour != int(cfg.get("run_hour", 2)):
                continue
            try:
                run_day = int(cfg.get("run_day_of_month", 1))
            except (TypeError, ValueError):
                run_day = 1
            run_day = max(1, min(run_day, 28))  # clamp to a day every month has
            if now_local.day != run_day:
                continue
            await enqueue_event(
                tenant_id=tool.tenant_id,
                event_type="tax_compliance_run",
                payload={},
                idempotency_key=f"tax_compliance:monthly:{tool.id}:{now_local.strftime('%Y-%m')}",
                db=db,
            )
            logger.info("tax_compliance_scheduled_fired tenant=%s tool=%s tz=%s", tool.tenant_id, tool.id, tz_name)
        except Exception as exc:
            logger.error("tax_compliance_cron_failed tenant=%s: %s", tool.tenant_id, type(exc).__name__)


async def expire_scheduled_payment_runs(_ctx: dict) -> None:
    """Hourly cron: auto-cancel scheduled payment runs whose approval window has elapsed."""
    from app.core.payouts import expire_due_payment_runs
    db = get_db()
    try:
        cancelled = await expire_due_payment_runs(db)
        if cancelled:
            logger.info("payment_runs_expired count=%d", cancelled)
    except Exception as exc:
        logger.error("payment_run_expiry_cron_failed: %s", type(exc).__name__)


async def run_reconciliation_scheduled_check(_ctx: dict) -> None:
    """Hourly cron: fires reconciliation_run for tools configured for daily or weekly frequency.
    Real-time frequency is handled separately via sync hooks in plaid/truelayer sync.
    """
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    from app.events import enqueue_event
    db = get_db()
    now_utc = datetime.now(UTC)

    tools = await db.tool.find_many(where={"type": "reconciliation", "status": "active"})
    for tool in tools:
        try:
            cfg = tool.config_json or {}
            frequency = cfg.get("reconciliation_frequency", "daily")
            if frequency == "real-time":
                continue

            tenant = await db.tenant.find_unique(where={"id": tool.tenant_id})
            tz_name = (tenant.timezone if tenant and tenant.timezone else None) or "UTC"
            try:
                tz = ZoneInfo(tz_name)
            except ZoneInfoNotFoundError:
                logger.warning("reconciliation_cron_unknown_tz tool=%s tz=%s — falling back to UTC", tool.id, tz_name)
                tz = UTC

            now_local = now_utc.astimezone(tz)
            current_hour = now_local.hour
            current_weekday = now_local.weekday()  # 0=Monday, 6=Sunday
            date_key = now_local.strftime("%Y-%m-%d")

            run_hour = int(cfg.get("run_hour", cfg.get("run_hour_utc", 2)))
            if current_hour != run_hour:
                continue

            if frequency == "weekly":
                day_value = cfg.get("run_day_of_week", "monday")
                run_day = _DAY_MAP.get(str(day_value).lower(), 0)
                if current_weekday != run_day:
                    continue
                idem_key = f"reconciliation:scheduled:{tool.id}:{date_key}"
                period_days = 7
            else:
                idem_key = f"reconciliation:scheduled:{tool.id}:{date_key}:{current_hour}"
                period_days = 30

            await enqueue_event(
                tenant_id=tool.tenant_id,
                event_type="reconciliation_run",
                payload={"period_days": period_days},
                idempotency_key=idem_key,
                db=db,
            )
            logger.info(
                "reconciliation_scheduled_fired tenant=%s tool=%s frequency=%s tz=%s",
                tool.tenant_id, tool.id, frequency, tz_name,
            )
        except Exception as exc:
            logger.error(
                "reconciliation_cron_failed tenant=%s tool=%s: %s",
                tool.tenant_id, tool.id, type(exc).__name__,
            )


async def startup(ctx: dict) -> None:
    settings = get_settings()
    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=0.1,
        )
        logger.info("sentry initialised for arq worker env=%s", settings.environment)
    await connect_db()
    logger.info("arq tool started")


async def shutdown(ctx: dict) -> None:
    await disconnect_db()
    logger.info("arq tool stopped")


class ToolSettings:
    functions = [
        run_invoice_received_job,
        run_receipt_received_job,
        run_document_received_job,
        run_reconciliation_scheduled_check,
        sync_quickbooks_connection,
        sync_plaid_transactions,
        reconcile_plaid_transactions,
        run_invoice_job,
        run_receipt_job,
        run_parse_invoice_job,
        run_parse_receipt_job,
        run_reconciliation_job,
        run_expense_control_job,
        run_accounts_payable_job,
        run_tax_compliance_job,
        run_financial_reporting_job,
        run_payment_run_job,
        run_document_intelligence_job,
        run_financial_reporting_monthly,
        run_payment_run_weekly,
        sync_xero_connection,
        sync_freshbooks_connection,
        sync_stripe_connection,
        sync_gocardless_connection,
        sync_square_connection,
        sync_paypal_connection,
        sync_truelayer_connection,
        sync_mono_transactions,
        reconcile_mono_transactions,
        sync_codat_connection,
        poll_codat_status,
        sync_gmail_connection,
        sync_drive_connection,
        sync_dropbox_connection,
        sync_outlook_connection,
        renew_outlook_subscriptions,
        sync_sage_connection,
        sync_adyen_connection,
        sync_wise_connection,
        sync_sap_connection,
        sync_netsuite_connection,
        sync_dynamics_connection,
        sync_onedrive_connection,
        fetch_exchange_rates_daily,
        run_month_end_close_job,
        run_month_end_close_scheduled,
        run_payroll_rec_job,
        run_journal_entry_job,
        resync_integrations_daily,
        expire_stale_approvals,
        run_ar_collections_job,
        run_ar_collections_scheduled,
        run_tax_compliance_scheduled,
        expire_scheduled_payment_runs,
    ]
    cron_jobs = [
        cron(run_financial_reporting_monthly, minute=0),  # hourly — gated by per-tool day-of-month/hour config
        cron(run_payment_run_weekly, minute=0),  # hourly — gated by per-tool weekday/hour config
        cron(fetch_exchange_rates_daily, hour=0, minute=5),
        cron(run_reconciliation_scheduled_check, minute=0),  # hourly
        cron(expire_stale_approvals, minute=5),  # hourly — auto-reject expired approvals
        cron(expire_scheduled_payment_runs, minute=15),  # hourly — auto-cancel expired payment runs
        cron(run_month_end_close_scheduled, hour=0, minute=10),  # daily midnight UTC
        cron(resync_integrations_daily, hour=3, minute=0),   # daily 3am UTC
        cron(run_ar_collections_scheduled, hour=8, minute=0),  # daily 8am UTC — chase overdue invoices
        cron(run_tax_compliance_scheduled, minute=0),  # hourly — gated by per-tool day-of-month/hour config
    ]
    on_startup = startup
    on_shutdown = shutdown

    redis_settings = RedisSettings.from_dsn(get_settings().redis_public_url)

    max_jobs = 10
    job_timeout = 900
    max_tries = 3
