"""
arq worker process — runs background jobs via Redis.
Start with: python -m arq app.worker.WorkerSettings
"""
import json
import time
from datetime import UTC, datetime, timedelta

from arq.connections import RedisSettings

from app.audit.logger import write_audit_log
from app.core.config import get_settings
from app.core.db import connect_db, disconnect_db, get_db
from app.core.logging import get_logger
from app.integrations.plaid.sync import reconcile_plaid_transactions, sync_plaid_transactions
from app.integrations.quickbooks.sync import sync_quickbooks_connection
from app.integrations.xero.sync import sync_xero_connection
from app.integrations.stripe.sync import sync_stripe_connection
from app.integrations.gocardless.sync import sync_gocardless_connection
from app.integrations.square.sync import sync_square_connection
from app.integrations.paypal.sync import sync_paypal_connection
from app.integrations.truelayer.sync import sync_truelayer_connection
from app.integrations.codat.sync import sync_codat_connection
from app.integrations.codat.sync import poll_codat_status
from app.integrations.hubspot.sync import sync_hubspot_connection
from app.integrations.google.sync_gmail import sync_gmail_connection
from app.integrations.google.sync_drive import sync_drive_connection
from app.integrations.outlook.sync import sync_outlook_connection
from app.integrations.outlook.sync import renew_outlook_subscriptions
from app.policy.engine import Decision, evaluate_policy
from app.queue.pool import get_queue_pool, push_to_dlq
from app.workers.ai_accountant import run_ai_accountant
from app.workers.invoice_processing import run_invoice_job
from app.workers.receipt_processing import run_receipt_job
from app.api.v1.parse.invoice import run_parse_invoice_job
from app.api.v1.parse.receipt import run_parse_receipt_job
from app.workers.fraud_detection import run_fraud_detection_job
from app.workers.collections import run_collections_job
from app.workers.revenue_recognition import run_revenue_recognition_job
from app.workers.credit_underwriting import run_credit_underwriting_job
from app.workers.compliance import run_compliance_job
from app.workers.reconciliation import run_reconciliation_job
from app.workers.expense_control import run_expense_control_job
from app.workers.treasury import run_treasury_job

logger = get_logger(__name__)


async def run_orchestrator_job(
    ctx: dict,
    *,
    execution_id: str,
    tenant_id: str,
    worker_id: str,
    event_type: str,
    payload: dict,
) -> dict:
    """
    arq job: routes a financial event through the orchestrator.
    Flow: classify → invoke worker → policy → audit → execution update.
    Audit is written before the execution record is updated (hard requirement).
    """
    db = get_db()
    start_ms = int(time.time() * 1000)

    try:
        await db.execution.update(
            where={"id": execution_id},
            data={"status": "running"},
        )

        if event_type == "transaction_posted":
            decision, confidence, reasoning = await _orchestrate_transaction_posted(
                payload, tenant_id, worker_id
            )
        elif event_type == "invoice_received":
            decision, confidence, reasoning = await _orchestrate_invoice_received(
                payload, tenant_id, worker_id
            )
        elif event_type == "fraud_check_requested":
            transaction_ids = payload.get("transaction_ids", [])
            if not transaction_ids:
                decision, confidence, reasoning = "blocked", 0.0, "No transaction_ids in payload"
            else:
                pool = await get_queue_pool()
                await pool.enqueue_job(
                    "run_fraud_detection_job",
                    execution_id=execution_id,
                    tenant_id=tenant_id,
                    worker_id=worker_id,
                    transaction_ids=transaction_ids,
                )
                decision, confidence, reasoning = (
                    "routed",
                    1.0,
                    f"Routed {len(transaction_ids)} transactions to Fraud Detection",
                )

        elif event_type == "collection_triggered":
            pool = await get_queue_pool()
            await pool.enqueue_job(
                "run_collections_job",
                execution_id=execution_id,
                tenant_id=tenant_id,
                worker_id=worker_id,
            )
            decision, confidence, reasoning = "routed", 1.0, "Routed to Collections worker"

        elif event_type == "revenue_recognition_run":
            pool = await get_queue_pool()
            await pool.enqueue_job(
                "run_revenue_recognition_job",
                execution_id=execution_id,
                tenant_id=tenant_id,
                worker_id=worker_id,
                contract_data=payload,
            )
            decision, confidence, reasoning = "routed", 1.0, "Routed to Revenue Recognition worker"

        elif event_type == "compliance_check_requested":
            pool = await get_queue_pool()
            await pool.enqueue_job(
                "run_compliance_job",
                execution_id=execution_id,
                tenant_id=tenant_id,
                worker_id=worker_id,
                transaction_ids=payload.get("transaction_ids", []),
                frameworks=payload.get("frameworks", ["AML", "KYC"]),
            )
            decision, confidence, reasoning = "routed", 1.0, "Routed to Compliance worker"

        elif event_type == "reconciliation_run":
            pool = await get_queue_pool()
            await pool.enqueue_job(
                "run_reconciliation_job",
                execution_id=execution_id,
                tenant_id=tenant_id,
                worker_id=worker_id,
                period_days=payload.get("period_days", 30),
            )
            decision, confidence, reasoning = "routed", 1.0, "Routed to Reconciliation worker"

        elif event_type == "expense_control_run":
            pool = await get_queue_pool()
            await pool.enqueue_job(
                "run_expense_control_job",
                execution_id=execution_id,
                tenant_id=tenant_id,
                worker_id=worker_id,
                transaction_ids=payload.get("transaction_ids", []),
            )
            decision, confidence, reasoning = "routed", 1.0, "Routed to Expense Control worker"

        elif event_type == "treasury_run":
            pool = await get_queue_pool()
            await pool.enqueue_job(
                "run_treasury_job",
                execution_id=execution_id,
                tenant_id=tenant_id,
                worker_id=worker_id,
            )
            decision, confidence, reasoning = "routed", 1.0, "Routed to Treasury worker"

        else:
            decision = "queued"
            confidence = 1.0
            reasoning = f"'{event_type}' routed — worker not yet implemented"

        duration_ms = int(time.time() * 1000) - start_ms

        # Audit BEFORE updating execution
        await write_audit_log(
            tenant_id=tenant_id,
            actor=f"orchestrator:{event_type}",
            action=f"event_routed:{decision}",
            reasoning_trace={
                "event_type": event_type,
                "worker_id": worker_id,
                "decision": decision,
                "confidence": confidence,
                "reasoning": reasoning,
                "payload_keys": list(payload.keys()),
                "duration_ms": duration_ms,
            },
            model_version="orchestrator-v1",
            execution_id=execution_id,
        )

        if decision == Decision.APPROVAL_REQUIRED.value:
            settings = get_settings()
            worker = await db.worker.find_unique(where={"id": worker_id})
            policy_config = (
                worker.config_json.get("policy", {})
                if worker and isinstance(worker.config_json, dict)
                else {}
            )
            ttl = policy_config.get("approval_ttl_seconds", settings.approval_ttl_seconds)
            existing_approval = await db.approval.find_first(where={"execution_id": execution_id})
            if not existing_approval:
                await db.approval.create(data={
                    "tenant_id": tenant_id,
                    "execution_id": execution_id,
                    "expires_at": datetime.now(UTC) + timedelta(seconds=ttl),
                })

        await db.execution.update(
            where={"id": execution_id},
            data={
                "status": "completed",
                "decision": decision,
                "confidence": confidence,
                "duration_ms": duration_ms,
            },
        )

        return {"status": "ok", "execution_id": execution_id, "decision": decision}

    except Exception as exc:
        logger.error(
            "orchestrator_job_failed",
            extra={"execution_id": execution_id, "event_type": event_type, "error": str(exc)},
        )
        try:
            await db.execution.update(
                where={"id": execution_id},
                data={"status": "failed", "decision": "failed"},
            )
        except Exception:
            pass

        job_try = ctx.get("job_try", 1)
        if job_try >= 3:
            await push_to_dlq(
                job_id=str(ctx.get("job_id", "unknown")),
                function_name="run_orchestrator_job",
                error=str(exc),
            )
        raise


async def _orchestrate_transaction_posted(
    payload: dict, tenant_id: str, worker_id: str
) -> tuple[str, float, str]:
    """Routes transaction_posted to the AI Accountant worker via arq."""
    transaction_ids = payload.get("transaction_ids", [])
    if not transaction_ids:
        return "blocked", 0.0, "No transaction_ids in payload"

    pool = await get_queue_pool()
    await pool.enqueue_job(
        "run_ai_accountant",
        transaction_ids=transaction_ids,
        tenant_id=tenant_id,
        worker_id=worker_id,
    )

    return "routed", 1.0, f"Routed {len(transaction_ids)} transactions to AI Accountant"


async def _orchestrate_invoice_received(
    payload: dict, tenant_id: str, worker_id: str
) -> tuple[str, float, str]:
    """Fetches a QB Invoice/Bill, applies policy, stores it, returns decision."""
    db = get_db()

    qb_entity = payload.get("qb_entity", "Invoice")
    qb_entity_id = payload.get("qb_entity_id", "")
    realm_id = payload.get("realm_id", "")
    integration_id = payload.get("integration_id", "")

    if not all([qb_entity_id, realm_id, integration_id]):
        return "blocked", 0.0, "Missing required QB invoice payload fields"

    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration or integration.status != "connected":
        return "blocked", 0.0, "QuickBooks integration not connected"

    try:
        from app.integrations.quickbooks import client as qb
        settings = get_settings()
        creds = json.loads(integration.encrypted_credentials)

        if qb_entity == "Invoice":
            entity_data = await qb.get_invoice(
                encrypted_access=creds["access_token"],
                realm_id=realm_id,
                invoice_id=qb_entity_id,
                sandbox=settings.quickbooks_sandbox,
            )
        else:
            entity_data = await qb.get_bill(
                encrypted_access=creds["access_token"],
                realm_id=realm_id,
                bill_id=qb_entity_id,
                sandbox=settings.quickbooks_sandbox,
            )
    except Exception as exc:
        return "blocked", 0.0, f"QB fetch failed: {type(exc).__name__}"

    if not entity_data:
        return "blocked", 0.0, "QB returned empty entity"

    worker = await db.worker.find_unique(where={"id": worker_id})
    policy_config = (
        worker.config_json.get("policy", {})
        if worker and isinstance(worker.config_json, dict)
        else {}
    )

    policy_result = evaluate_policy(
        amount_minor=entity_data.get("amount_minor", 0),
        currency=entity_data.get("currency", "GBP"),
        vendor=entity_data.get("vendor", "unknown"),
        verified_suppliers=policy_config.get("verified_suppliers", []),
        allowed_currencies=policy_config.get("allowed_currencies", ["GBP", "USD", "EUR"]),
        auto_threshold_minor=policy_config.get("auto_threshold", 50000),
        block_threshold_minor=policy_config.get("approve_threshold", 500000),
    )

    # Store invoice only if not already present
    invoice_number = entity_data.get("invoice_number", qb_entity_id)
    existing = await db.invoice.find_first(
        where={"tenant_id": tenant_id, "invoice_number": invoice_number}
    )
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

    reasoning = (
        f"QB {qb_entity} {qb_entity_id} | vendor={entity_data.get('vendor', 'unknown')} "
        f"| {policy_result.reason} | rule={policy_result.rule_triggered}"
    )
    return policy_result.decision.value, 0.95, reasoning


async def startup(ctx: dict) -> None:
    await connect_db()
    logger.info("arq worker started")


async def shutdown(ctx: dict) -> None:
    await disconnect_db()
    logger.info("arq worker stopped")


class WorkerSettings:
    functions = [
        run_orchestrator_job,
        sync_quickbooks_connection,
        sync_plaid_transactions,
        reconcile_plaid_transactions,
        run_ai_accountant,
        run_invoice_job,
        run_receipt_job,
        run_parse_invoice_job,
        run_parse_receipt_job,
        run_fraud_detection_job,
        run_collections_job,
        run_revenue_recognition_job,
        run_credit_underwriting_job,
        run_compliance_job,
        run_reconciliation_job,
        run_expense_control_job,
        run_treasury_job,
        sync_xero_connection,
        sync_stripe_connection,
        sync_gocardless_connection,
        sync_square_connection,
        sync_paypal_connection,
        sync_truelayer_connection,
        sync_codat_connection,
        poll_codat_status,
        sync_hubspot_connection,
        sync_gmail_connection,
        sync_drive_connection,
        sync_outlook_connection,
        renew_outlook_subscriptions,
    ]
    on_startup = startup
    on_shutdown = shutdown

    @property
    def redis_settings(self) -> RedisSettings:
        settings = get_settings()
        return RedisSettings.from_dsn(settings.redis_url)

    max_jobs = 10
    job_timeout = 300
    max_tries = 3
