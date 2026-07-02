"""
arq tool process — runs background jobs via Redis.
Start with: python -m arq app.tool.ToolSettings
"""
import base64
import time
from datetime import UTC, datetime, timedelta

from arq import cron
from arq.connections import RedisSettings

from app.audit.logger import write_audit_log
from app.core.config import get_settings
from app.core.db import connect_db, disconnect_db, get_db
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
from app.integrations.hubspot.sync import sync_hubspot_connection
from app.integrations.google.sync_gmail import sync_gmail_connection
from app.integrations.google.sync_drive import sync_drive_connection
from app.integrations.dropbox.sync import sync_dropbox_connection
from app.integrations.outlook.sync import sync_outlook_connection
from app.integrations.outlook.sync import renew_outlook_subscriptions
from app.integrations.sage.sync import sync_sage_connection
from app.integrations.adyen.sync import sync_adyen_connection
from app.integrations.wise.sync import sync_wise_connection
from app.integrations.exchange_rates.service import fetch_exchange_rates_daily
from app.policy.engine import Decision, evaluate_policy
from app.queue.pool import get_queue_pool, push_to_dlq
from app.tools.ai_accountant import run_ai_accountant
from app.tools.invoice_processing import run_invoice_job
from app.tools.receipt_processing import run_receipt_job
from app.api.v1.parse.invoice import run_parse_invoice_job
from app.api.v1.parse.receipt import run_parse_receipt_job
from app.tools.fraud_detection import run_fraud_detection_job
from app.tools.collections import run_collections_job
from app.tools.revenue_recognition import run_revenue_recognition_job
from app.tools.credit_underwriting import run_credit_underwriting_job
from app.tools.compliance import run_compliance_job
from app.tools.reconciliation import run_reconciliation_job
from app.tools.expense_control import run_expense_control_job
from app.tools.treasury import run_treasury_job
from app.tools.accounts_receivable import run_accounts_receivable_job
from app.tools.accounts_payable import run_accounts_payable_job
from app.tools.cash_flow_forecast import run_cash_flow_forecast_job
from app.tools.tax_compliance import run_tax_compliance_job
from app.tools.financial_reporting import run_financial_reporting_job
from app.tools.payment_run import run_payment_run_job
from app.tools.budgeting import run_budgeting_job
from app.tools.document_intelligence import run_document_intelligence_job
from app.tools.month_end_close import run_month_end_close_job, run_month_end_close_scheduled
from app.tools.payroll_reconciliation import run_payroll_rec_job
from app.tools.journal_entries import run_journal_entry_job

logger = get_logger(__name__)

_DAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def _apply_autonomy_override(decision: str, autonomy_level: str) -> str:
    """Override policy decision based on tool autonomy level.
    auto: promote approval_required → auto_approved (blocked is never overridden).
    approve: no change.
    """
    if decision == Decision.BLOCKED.value:
        return decision
    if autonomy_level == "auto" and decision == Decision.APPROVAL_REQUIRED.value:
        return Decision.AUTO_APPROVED.value
    return decision


async def run_orchestrator_job(
    ctx: dict,
    *,
    execution_id: str,
    tenant_id: str,
    tool_id: str,
    event_type: str,
    payload: dict,
) -> dict:
    """
    arq job: routes a financial event through the orchestrator.
    Flow: classify → invoke tool → policy → audit → execution update.
    Audit is written before the execution record is updated (hard requirement).
    """
    db = get_db()
    start_ms = int(time.time() * 1000)
    logger.info(
        "orchestrator_job_start",
        extra={
            "execution_id": execution_id,
            "event_type": event_type,
            "tool_id": tool_id,
            "tenant_id": tenant_id,
            "payload_keys": list(payload.keys()),
        },
    )

    try:
        await db.execution.update(
            where={"id": execution_id},
            data={"status": "running"},
        )

        if event_type == "transaction_posted":
            logger.info(
                "orchestrator_dispatching",
                extra={"execution_id": execution_id, "event_type": event_type, "tool_id": tool_id},
            )
            decision, confidence, reasoning = await _orchestrate_transaction_posted(
                payload, tenant_id, tool_id, execution_id
            )
            logger.info(
                "orchestrator_dispatch_done",
                extra={
                    "execution_id": execution_id,
                    "decision": decision,
                    "confidence": confidence,
                },
            )
        elif event_type == "invoice_received":
            decision, confidence, reasoning = await _orchestrate_invoice_received(
                payload, tenant_id, tool_id
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
                    tool_id=tool_id,
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
                tool_id=tool_id,
            )
            decision, confidence, reasoning = "routed", 1.0, "Routed to Collections tool"

        elif event_type == "revenue_recognition_run":
            pool = await get_queue_pool()
            await pool.enqueue_job(
                "run_revenue_recognition_job",
                execution_id=execution_id,
                tenant_id=tenant_id,
                tool_id=tool_id,
                contract_data=payload,
            )
            decision, confidence, reasoning = "routed", 1.0, "Routed to Revenue Recognition tool"

        elif event_type == "compliance_check_requested":
            pool = await get_queue_pool()
            await pool.enqueue_job(
                "run_compliance_job",
                execution_id=execution_id,
                tenant_id=tenant_id,
                tool_id=tool_id,
                transaction_ids=payload.get("transaction_ids", []),
                frameworks=payload.get("frameworks", ["AML", "KYC"]),
            )
            decision, confidence, reasoning = "routed", 1.0, "Routed to Compliance tool"

        elif event_type == "reconciliation_run":
            from app.tools.reconciliation import _execute_reconciliation

            def _parse_dt(val: str | None) -> datetime | None:
                if not val:
                    return None
                try:
                    dt = datetime.fromisoformat(str(val))
                    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
                except (ValueError, TypeError):
                    return None

            result = await _execute_reconciliation(
                tenant_id=tenant_id,
                tool_id=tool_id,
                execution_id=execution_id,
                period_days=payload.get("period_days", 30),
                period_start=_parse_dt(payload.get("period_start")),
                period_end=_parse_dt(payload.get("period_end")),
                policy_overrides=payload.get("policy") if isinstance(payload.get("policy"), dict) else None,
            )
            # _execute_reconciliation writes its own audit log and ReconciliationRun record.
            # Apply autonomy override then update execution directly — no second queue hop.
            real_decision = result["decision"]
            _tool_rec = await db.tool.find_unique(where={"id": tool_id})
            if _tool_rec and real_decision != Decision.BLOCKED.value:
                overridden = _apply_autonomy_override(real_decision, _tool_rec.autonomy_level)
                if overridden != real_decision:
                    real_decision = overridden

            duration_ms_recon = int(time.time() * 1000) - start_ms
            if real_decision == Decision.APPROVAL_REQUIRED.value:
                _settings = get_settings()
                existing_approval = await db.approval.find_first(where={"execution_id": execution_id})
                if not existing_approval:
                    await db.approval.create(data={
                        "tenant_id": tenant_id,
                        "execution_id": execution_id,
                        "expires_at": datetime.now(UTC) + timedelta(seconds=_settings.approval_ttl_seconds),
                    })
            await db.execution.update(
                where={"id": execution_id},
                data={
                    "status": "completed",
                    "decision": real_decision,
                    "confidence": result["confidence"],
                    "duration_ms": duration_ms_recon,
                },
            )
            return {"status": "ok", "execution_id": execution_id, "decision": real_decision}

        elif event_type == "expense_control_run":
            pool = await get_queue_pool()
            await pool.enqueue_job(
                "run_expense_control_job",
                execution_id=execution_id,
                tenant_id=tenant_id,
                tool_id=tool_id,
                transaction_ids=payload.get("transaction_ids", []),
            )
            decision, confidence, reasoning = "routed", 1.0, "Routed to Expense Control tool"

        elif event_type == "treasury_run":
            pool = await get_queue_pool()
            await pool.enqueue_job(
                "run_treasury_job",
                execution_id=execution_id,
                tenant_id=tenant_id,
                tool_id=tool_id,
            )
            decision, confidence, reasoning = "routed", 1.0, "Routed to Treasury tool"

        elif event_type == "ar_run":
            pool = await get_queue_pool()
            await pool.enqueue_job(
                "run_accounts_receivable_job",
                execution_id=execution_id,
                tenant_id=tenant_id,
                tool_id=tool_id,
                payload=payload,
                policy_config=payload.get("policy_config", {}),
            )
            decision, confidence, reasoning = "routed", 1.0, "Routed to Accounts Receivable tool"

        elif event_type == "ap_run":
            pool = await get_queue_pool()
            await pool.enqueue_job(
                "run_accounts_payable_job",
                execution_id=execution_id,
                tenant_id=tenant_id,
                tool_id=tool_id,
                payload=payload,
                policy_config=payload.get("policy_config", {}),
            )
            decision, confidence, reasoning = "routed", 1.0, "Routed to Accounts Payable tool"

        elif event_type == "cash_flow_run":
            pool = await get_queue_pool()
            await pool.enqueue_job(
                "run_cash_flow_forecast_job",
                execution_id=execution_id,
                tenant_id=tenant_id,
                tool_id=tool_id,
                payload=payload,
                policy_config=payload.get("policy_config", {}),
            )
            decision, confidence, reasoning = "routed", 1.0, "Routed to Cash Flow Forecast tool"

        elif event_type == "tax_compliance_run":
            pool = await get_queue_pool()
            await pool.enqueue_job(
                "run_tax_compliance_job",
                execution_id=execution_id,
                tenant_id=tenant_id,
                tool_id=tool_id,
                payload=payload,
                policy_config=payload.get("policy_config", {}),
            )
            decision, confidence, reasoning = "routed", 1.0, "Routed to Tax Compliance tool"

        elif event_type == "document_received":
            _tool_for_dispatch = await db.tool.find_unique(where={"id": tool_id})
            if _tool_for_dispatch and _tool_for_dispatch.type == "document_intelligence":
                raw_bytes = payload.get("file_bytes", b"")
                if isinstance(raw_bytes, str):
                    raw_bytes = base64.b64decode(raw_bytes) if raw_bytes else b""
                if raw_bytes:
                    document_type = payload.get("document_type", "document")
                    content_type_val = payload.get("content_type", "application/pdf")
                    doc_record = await db.document.create(data={
                        "tenant_id": tenant_id,
                        "tool_id": tool_id,
                        "document_type": "pending",
                        "filename": payload.get("filename", ""),
                        "content_type": content_type_val,
                        "file_size_bytes": len(raw_bytes),
                        "uploaded_by": payload.get("source", "integration"),
                        "status": "processing",
                        "execution_id": execution_id,
                    })
                    pool = await get_queue_pool()
                    await pool.enqueue_job(
                        "run_document_intelligence_job",
                        execution_id=execution_id,
                        tenant_id=tenant_id,
                        tool_id=tool_id,
                        file_bytes=raw_bytes,
                        content_type=content_type_val,
                        document_id=doc_record.id,
                    )
                    decision, confidence, reasoning = (
                        "routed", 1.0, f"Routed {document_type} to Document Intelligence"
                    )
                else:
                    decision, confidence, reasoning = await _orchestrate_document_intelligence_received(
                        payload, tenant_id, tool_id, execution_id
                    )
            else:
                document_type = payload.get("document_type", "invoice")
                if document_type == "receipt":
                    decision, confidence, reasoning = await _orchestrate_receipt_received(
                        payload, tenant_id, tool_id, execution_id
                    )
                else:
                    decision, confidence, reasoning = await _orchestrate_invoice_received(
                        payload, tenant_id, tool_id
                    )

        elif event_type == "spend_control_run":
            pool = await get_queue_pool()
            transaction_ids = payload.get("transaction_ids", [])
            await pool.enqueue_job(
                "run_expense_control_job",
                execution_id=execution_id,
                tenant_id=tenant_id,
                tool_id=tool_id,
                transaction_ids=transaction_ids,
            )
            await pool.enqueue_job(
                "run_accounts_payable_job",
                execution_id=execution_id,
                tenant_id=tenant_id,
                tool_id=tool_id,
                payload=payload,
                policy_config=payload.get("policy_config", {}),
            )
            decision, confidence, reasoning = "routed", 1.0, "Routed to Spend Control (expense + AP)"

        elif event_type == "ar_collections_run":
            pool = await get_queue_pool()
            await pool.enqueue_job(
                "run_accounts_receivable_job",
                execution_id=execution_id,
                tenant_id=tenant_id,
                tool_id=tool_id,
                payload=payload,
                policy_config=payload.get("policy_config", {}),
            )
            await pool.enqueue_job(
                "run_collections_job",
                execution_id=execution_id,
                tenant_id=tenant_id,
                tool_id=tool_id,
            )
            decision, confidence, reasoning = "routed", 1.0, "Routed to AR & Collections"

        elif event_type == "risk_compliance_run":
            pool = await get_queue_pool()
            transaction_ids = payload.get("transaction_ids", [])
            frameworks = payload.get("frameworks", ["AML", "KYC"])
            await pool.enqueue_job(
                "run_compliance_job",
                execution_id=execution_id,
                tenant_id=tenant_id,
                tool_id=tool_id,
                transaction_ids=transaction_ids,
                frameworks=frameworks,
            )
            if transaction_ids:
                await pool.enqueue_job(
                    "run_fraud_detection_job",
                    execution_id=execution_id,
                    tenant_id=tenant_id,
                    tool_id=tool_id,
                    transaction_ids=transaction_ids,
                )
            decision, confidence, reasoning = "routed", 1.0, "Routed to Risk & Compliance"

        elif event_type == "treasury_cash_run":
            pool = await get_queue_pool()
            await pool.enqueue_job(
                "run_treasury_job",
                execution_id=execution_id,
                tenant_id=tenant_id,
                tool_id=tool_id,
            )
            await pool.enqueue_job(
                "run_cash_flow_forecast_job",
                execution_id=execution_id,
                tenant_id=tenant_id,
                tool_id=tool_id,
                payload=payload,
                policy_config=payload.get("policy_config", {}),
            )
            decision, confidence, reasoning = "routed", 1.0, "Routed to Treasury & Cash"

        elif event_type == "receipt_received":
            decision, confidence, reasoning = await _orchestrate_receipt_received(
                payload, tenant_id, tool_id, execution_id
            )

        elif event_type == "credit_assessment_run":
            pool = await get_queue_pool()
            await pool.enqueue_job(
                "run_credit_underwriting_job",
                execution_id=execution_id,
                tenant_id=tenant_id,
                tool_id=tool_id,
                application_data=payload,
            )
            decision, confidence, reasoning = "routed", 1.0, "Routed to Credit Underwriting"

        elif event_type == "financial_report_run":
            pool = await get_queue_pool()
            await pool.enqueue_job(
                "run_financial_reporting_job",
                execution_id=execution_id,
                tenant_id=tenant_id,
                tool_id=tool_id,
                payload=payload,
                policy_config=payload.get("policy_config", {}),
            )
            decision, confidence, reasoning = "routed", 1.0, "Routed to Financial Reporting"

        elif event_type == "payment_run_requested":
            pool = await get_queue_pool()
            await pool.enqueue_job(
                "run_payment_run_job",
                execution_id=execution_id,
                tenant_id=tenant_id,
                tool_id=tool_id,
                payload=payload,
                policy_config=payload.get("policy_config", {}),
            )
            decision, confidence, reasoning = "routed", 1.0, "Routed to Payment Run"

        elif event_type == "budget_check_run":
            pool = await get_queue_pool()
            await pool.enqueue_job(
                "run_budgeting_job",
                execution_id=execution_id,
                tenant_id=tenant_id,
                tool_id=tool_id,
                payload=payload,
                policy_config=payload.get("policy_config", {}),
            )
            decision, confidence, reasoning = "routed", 1.0, "Routed to Budgeting"

        else:
            decision = "queued"
            confidence = 1.0
            reasoning = f"'{event_type}' routed — tool not yet implemented"

        duration_ms = int(time.time() * 1000) - start_ms

        # Apply autonomy level override for inline policy decisions (not routed/queued)
        if decision not in (Decision.BLOCKED.value, "routed", "queued"):
            _tool_rec = await db.tool.find_unique(where={"id": tool_id})
            if _tool_rec:
                overridden = _apply_autonomy_override(decision, _tool_rec.autonomy_level)
                if overridden != decision:
                    reasoning = f"[autonomy={_tool_rec.autonomy_level}: {decision}→{overridden}] {reasoning}"
                    decision = overridden

        # Audit BEFORE updating execution
        logger.info(
            "orchestrator_audit_write",
            extra={"execution_id": execution_id, "decision": decision, "duration_ms": duration_ms},
        )
        await write_audit_log(
            tenant_id=tenant_id,
            actor=f"orchestrator:{event_type}",
            action=f"event_routed:{decision}",
            reasoning_trace={
                "event_type": event_type,
                "tool_id": tool_id,
                "decision": decision,
                "confidence": confidence,
                "reasoning": reasoning,
                "payload_keys": list(payload.keys()),
                "duration_ms": duration_ms,
            },
            model_version="orchestrator-v1",
            execution_id=execution_id,
        )
        logger.info("orchestrator_audit_done", extra={"execution_id": execution_id})

        if decision == Decision.APPROVAL_REQUIRED.value:
            settings = get_settings()
            tool = await db.tool.find_unique(where={"id": tool_id})
            policy_config = (
                tool.config_json.get("policy", {})
                if tool and isinstance(tool.config_json, dict)
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

        final_status = "cancelled" if decision == "cancelled" else "completed"
        await db.execution.update(
            where={"id": execution_id},
            data={
                "status": final_status,
                "decision": decision,
                "confidence": confidence,
                "duration_ms": duration_ms,
            },
        )

        return {"status": "ok", "execution_id": execution_id, "decision": decision}

    except BaseException as exc:
        logger.error(
            "orchestrator_job_failed",
            extra={"execution_id": execution_id, "event_type": event_type, "error": str(exc)},
            exc_info=True,
        )
        try:
            await db.execution.update(
                where={"id": execution_id},
                data={"status": "failed", "decision": "failed", "error_message": str(exc)[:2000]},
            )
        except Exception:
            pass

        job_try = ctx.get("job_try", 1)
        if isinstance(exc, Exception) and job_try >= 3:
            await push_to_dlq(
                job_id=str(ctx.get("job_id", "unknown")),
                function_name="run_orchestrator_job",
                error=str(exc),
            )
        raise


async def _orchestrate_transaction_posted(
    payload: dict, tenant_id: str, tool_id: str, execution_id: str
) -> tuple[str, float, str]:
    """Runs the AI Accountant inline so the execution record reflects the real result."""
    from app.tools.ai_accountant import AIAccountantTool
    transaction_ids = payload.get("transaction_ids", [])
    logger.info(
        "transaction_posted_enter",
        extra={
            "execution_id": execution_id,
            "tool_id": tool_id,
            "transaction_count": len(transaction_ids),
        },
    )
    db = get_db()
    if not transaction_ids:
        logger.info("transaction_posted_fetch_all_pending", extra={"execution_id": execution_id, "tenant_id": tenant_id})
        pending_txns = await db.banktransaction.find_many(
            where={
                "tenant_id": tenant_id,
                "AND": [
                    {"NOT": {"status": {"equals": "categorised"}}},
                    {"NOT": {"status": {"equals": "matched"}}},
                ],
            },
            take=2000,
            order={"date": "desc"},
        )
        transaction_ids = [t.id for t in pending_txns]
        if not transaction_ids:
            logger.info("transaction_posted_nothing_pending", extra={"execution_id": execution_id})
            return "blocked", 0.0, "No pending transactions to categorise"
        logger.info("transaction_posted_all_pending", extra={"execution_id": execution_id, "count": len(transaction_ids)})
    tool_record = await db.tool.find_unique(where={"id": tool_id})
    policy_config = (
        tool_record.config_json if tool_record and isinstance(tool_record.config_json, dict) else {}
    )
    logger.info(
        "transaction_posted_policy_loaded",
        extra={"execution_id": execution_id, "policy_keys": list(policy_config.keys())},
    )

    result = await AIAccountantTool().run(
        transaction_ids=transaction_ids,
        tenant_id=tenant_id,
        tool_id=tool_id,
        policy_config=policy_config,
        execution_id=execution_id,
    )

    n = len(result.results)
    logger.info(
        "transaction_posted_done",
        extra={
            "execution_id": execution_id,
            "categorised": n,
            "of_total": len(transaction_ids),
            "decision": result.decision,
            "confidence": result.confidence,
        },
    )
    return result.decision, result.confidence, f"Categorised {n} of {len(transaction_ids)} transactions"


async def _orchestrate_invoice_received(
    payload: dict, tenant_id: str, tool_id: str
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
        from app.integrations.encryption import decrypt_credentials as _dc
        settings = get_settings()
        creds = _dc(integration.encrypted_credentials, tenant_id)

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

    tool = await db.tool.find_unique(where={"id": tool_id})
    policy_config = (
        tool.config_json.get("policy", {})
        if tool and isinstance(tool.config_json, dict)
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


async def _orchestrate_receipt_received(
    payload: dict, tenant_id: str, tool_id: str, execution_id: str
) -> tuple[str, float, str]:
    """Fetches receipt bytes from the source integration and enqueues run_receipt_job."""
    source = payload.get("source", "")
    integration_id = payload.get("integration_id", "")

    if not source or not integration_id:
        return "blocked", 0.0, "Missing source or integration_id in receipt payload"

    db = get_db()
    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration or integration.status != "connected":
        return "blocked", 0.0, "Source integration not connected"
    if integration.tenant_id != tenant_id:
        return "blocked", 0.0, "Tenant mismatch on receipt source integration"

    from app.integrations.encryption import decrypt_credentials
    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    except Exception:
        return "blocked", 0.0, "Failed to decrypt integration credentials"

    access_token = creds.get("access_token", "")
    if not access_token:
        return "blocked", 0.0, "No access token in integration credentials"

    file_bytes: bytes = b""
    content_type = "application/pdf"

    try:
        if source == "gmail":
            from app.integrations.google import client as google
            message_id = payload.get("message_id", "")
            attachment_id = payload.get("attachment_id", "")
            if not message_id or not attachment_id:
                return "blocked", 0.0, "Missing message_id or attachment_id for Gmail receipt"
            file_bytes = await google.get_gmail_attachment_bytes(access_token, message_id, attachment_id)

        elif source == "google_drive":
            from app.integrations.google import client as google
            file_id = payload.get("file_id", "")
            if not file_id:
                return "blocked", 0.0, "Missing file_id for Drive receipt"
            file_bytes = await google.download_drive_file_bytes(access_token, file_id)

        elif source == "outlook":
            from app.integrations.outlook import client as outlook_client
            message_id = payload.get("message_id", "")
            if not message_id:
                return "blocked", 0.0, "Missing message_id for Outlook receipt"
            attachments = await outlook_client.get_message_attachments(access_token, message_id)
            pdf_attachment = next(
                (a for a in attachments if "pdf" in a.get("contentType", "").lower()
                 or a.get("name", "").lower().endswith(".pdf")),
                None,
            )
            if not pdf_attachment:
                return "blocked", 0.0, "No PDF attachment found in Outlook message"
            file_bytes, content_type = await outlook_client.get_attachment_bytes(
                access_token, message_id, pdf_attachment["id"]
            )

        else:
            return "blocked", 0.0, f"Unknown receipt source: {source}"

    except Exception as exc:
        return "blocked", 0.0, f"Failed to fetch receipt from {source}: {type(exc).__name__}"

    if not file_bytes:
        return "blocked", 0.0, "Empty receipt file returned from source"

    tool = await db.tool.find_unique(where={"id": tool_id})
    policy_config = (
        tool.config_json.get("policy", {})
        if tool and isinstance(tool.config_json, dict)
        else {}
    )

    pool = await get_queue_pool()
    await pool.enqueue_job(
        "run_receipt_job",
        execution_id=execution_id,
        tenant_id=tenant_id,
        tool_id=tool_id,
        file_bytes=file_bytes,
        content_type=content_type,
        policy_config=policy_config,
    )
    return "routed", 1.0, f"Receipt fetched from {source} and queued for processing"


async def _orchestrate_document_intelligence_received(
    payload: dict, tenant_id: str, tool_id: str, execution_id: str
) -> tuple[str, float, str]:
    """Fetches document bytes from the source integration, creates a Document record,
    and enqueues run_document_intelligence_job."""
    from app.tools.document_intelligence import _ALLOWED_CONTENT_TYPES, _generate_thumbnail

    source = payload.get("source", "")
    integration_id = payload.get("integration_id", "")
    document_type = payload.get("document_type", "invoice")
    filename = payload.get("filename")

    if not source or not integration_id:
        return "blocked", 0.0, "Missing source or integration_id in document payload"

    db = get_db()
    integration = await db.integration.find_unique(where={"id": integration_id})
    if not integration or integration.status != "connected":
        return "blocked", 0.0, "Source integration not connected"
    if integration.tenant_id != tenant_id:
        return "blocked", 0.0, "Tenant mismatch on document source integration"

    from app.integrations.encryption import decrypt_credentials
    try:
        creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    except Exception:
        return "blocked", 0.0, "Failed to decrypt integration credentials"

    access_token = creds.get("access_token", "")
    if not access_token:
        return "blocked", 0.0, "No access token in integration credentials"

    file_bytes: bytes = b""
    content_type = "application/pdf"

    try:
        if source == "gmail":
            from app.integrations.google import client as google
            message_id = payload.get("message_id", "")
            attachment_id = payload.get("attachment_id", "")
            if not message_id or not attachment_id:
                return "blocked", 0.0, "Missing message_id or attachment_id for Gmail document"
            file_bytes = await google.get_gmail_attachment_bytes(access_token, message_id, attachment_id)

        elif source == "google_drive":
            from app.integrations.google import client as google
            file_id = payload.get("file_id", "")
            if not file_id:
                return "blocked", 0.0, "Missing file_id for Drive document"
            file_bytes = await google.download_drive_file_bytes(access_token, file_id)

        elif source == "outlook":
            from app.integrations.outlook import client as outlook_client
            message_id = payload.get("message_id", "")
            if not message_id:
                return "blocked", 0.0, "Missing message_id for Outlook document"
            attachments = await outlook_client.get_message_attachments(access_token, message_id)
            pdf_attachment = next(
                (a for a in attachments if "pdf" in a.get("contentType", "").lower()
                 or a.get("name", "").lower().endswith(".pdf")),
                None,
            )
            if not pdf_attachment:
                return "blocked", 0.0, "No PDF attachment found in Outlook message"
            file_bytes, content_type = await outlook_client.get_attachment_bytes(
                access_token, message_id, pdf_attachment["id"]
            )
            if not filename:
                filename = pdf_attachment.get("name")

        else:
            return "blocked", 0.0, f"Unknown document source: {source}"

    except Exception as exc:
        return "blocked", 0.0, f"Failed to fetch document from {source}: {type(exc).__name__}"

    if not file_bytes:
        return "blocked", 0.0, "Empty document file returned from source"

    if content_type not in _ALLOWED_CONTENT_TYPES:
        content_type = "application/pdf"

    tool = await db.tool.find_unique(where={"id": tool_id})
    policy_config = tool.config_json if tool and isinstance(tool.config_json, dict) else {}

    thumbnail_b64 = _generate_thumbnail(file_bytes, content_type)

    doc_record = await db.document.create(data={
        "tenant_id": tenant_id,
        "tool_id": tool_id,
        "execution_id": execution_id,
        "document_type": document_type,
        "filename": filename,
        "content_type": content_type,
        "file_size_bytes": len(file_bytes),
        "status": "processing",
        "thumbnail_b64": thumbnail_b64,
    })

    pool = await get_queue_pool()
    await pool.enqueue_job(
        "run_document_intelligence_job",
        execution_id=execution_id,
        tenant_id=tenant_id,
        tool_id=tool_id,
        file_bytes=file_bytes,
        content_type=content_type,
        policy_config=policy_config,
        document_id=doc_record.id,
    )
    return "routed", 1.0, f"Document fetched from {source} and queued for intelligence processing"


async def run_revenue_recognition_monthly(ctx: dict) -> None:
    """Monthly cron: fires revenue_recognition_run for all tenants with active tools."""
    db = get_db()
    from app.orchestrator.events import enqueue_orchestrator_event
    tools = await db.tool.find_many(
        where={"type": "revenue_recognition", "status": "active"}
    )
    month_key = datetime.now(UTC).strftime("%Y-%m")
    for tool in tools:
        try:
            await enqueue_orchestrator_event(
                tenant_id=tool.tenant_id,
                event_type="revenue_recognition_run",
                payload={},
                idempotency_key=f"revenue_recognition:monthly:{tool.tenant_id}:{month_key}",
                db=db,
            )
        except Exception as exc:
            logger.error(
                "revenue_recognition_cron_failed tenant=%s: %s",
                tool.tenant_id, type(exc).__name__,
            )


async def run_financial_reporting_monthly(ctx: dict) -> None:
    """Monthly cron: fires financial_report_run for all tenants with active tools."""
    db = get_db()
    from app.orchestrator.events import enqueue_orchestrator_event
    tools = await db.tool.find_many(where={"type": "financial_reporting", "status": "active"})
    month_key = datetime.now(UTC).strftime("%Y-%m")
    for tool in tools:
        try:
            await enqueue_orchestrator_event(
                tenant_id=tool.tenant_id,
                event_type="financial_report_run",
                payload={},
                idempotency_key=f"financial_reporting:monthly:{tool.tenant_id}:{month_key}",
                db=db,
            )
        except Exception as exc:
            logger.error("financial_reporting_cron_failed tenant=%s: %s", tool.tenant_id, type(exc).__name__)


async def run_payment_run_weekly(ctx: dict) -> None:
    """Weekly cron: fires payment_run_requested for all tenants with active tools."""
    db = get_db()
    from app.orchestrator.events import enqueue_orchestrator_event
    tools = await db.tool.find_many(where={"type": "payment_run", "status": "active"})
    week_key = datetime.now(UTC).strftime("%Y-W%W")
    for tool in tools:
        try:
            await enqueue_orchestrator_event(
                tenant_id=tool.tenant_id,
                event_type="payment_run_requested",
                payload={},
                idempotency_key=f"payment_run:weekly:{tool.tenant_id}:{week_key}",
                db=db,
            )
        except Exception as exc:
            logger.error("payment_run_cron_failed tenant=%s: %s", tool.tenant_id, type(exc).__name__)


async def run_budget_check_weekly(ctx: dict) -> None:
    """Weekly cron: fires budget_check_run for all tenants with active tools."""
    db = get_db()
    from app.orchestrator.events import enqueue_orchestrator_event
    tools = await db.tool.find_many(where={"type": "budgeting", "status": "active"})
    week_key = datetime.now(UTC).strftime("%Y-W%W")
    for tool in tools:
        try:
            await enqueue_orchestrator_event(
                tenant_id=tool.tenant_id,
                event_type="budget_check_run",
                payload={},
                idempotency_key=f"budgeting:weekly:{tool.tenant_id}:{week_key}",
                db=db,
            )
        except Exception as exc:
            logger.error("budget_check_cron_failed tenant=%s: %s", tool.tenant_id, type(exc).__name__)


_INTEGRATION_SYNC_JOBS: dict[str, str] = {
    "quickbooks":  "sync_quickbooks_connection",
    "xero":        "sync_xero_connection",
    "freshbooks":  "sync_freshbooks_connection",
    "stripe":      "sync_stripe_connection",
    "gocardless":  "sync_gocardless_connection",
    "square":      "sync_square_connection",
    "paypal":      "sync_paypal_connection",
}


async def resync_integrations_daily(_ctx: dict) -> None:
    """Daily cron: re-enqueues sync jobs for all connected accounting and payment integrations."""
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


async def run_reconciliation_scheduled_check(_ctx: dict) -> None:
    """Hourly cron: fires reconciliation_run for tools configured for daily or weekly frequency.
    Real-time frequency is handled separately via sync hooks in plaid/truelayer sync.
    """
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    from app.orchestrator.events import enqueue_orchestrator_event
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

            await enqueue_orchestrator_event(
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
    await connect_db()
    logger.info("arq tool started")


async def shutdown(ctx: dict) -> None:
    await disconnect_db()
    logger.info("arq tool stopped")


class ToolSettings:
    functions = [
        run_orchestrator_job,
        run_revenue_recognition_monthly,
        run_reconciliation_scheduled_check,
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
        run_accounts_receivable_job,
        run_accounts_payable_job,
        run_cash_flow_forecast_job,
        run_tax_compliance_job,
        run_financial_reporting_job,
        run_payment_run_job,
        run_budgeting_job,
        run_document_intelligence_job,
        run_financial_reporting_monthly,
        run_payment_run_weekly,
        run_budget_check_weekly,
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
        sync_hubspot_connection,
        sync_gmail_connection,
        sync_drive_connection,
        sync_dropbox_connection,
        sync_outlook_connection,
        renew_outlook_subscriptions,
        sync_sage_connection,
        sync_adyen_connection,
        sync_wise_connection,
        fetch_exchange_rates_daily,
        run_month_end_close_job,
        run_month_end_close_scheduled,
        run_payroll_rec_job,
        run_journal_entry_job,
        resync_integrations_daily,
    ]
    cron_jobs = [
        cron(run_revenue_recognition_monthly, day=1, hour=0, minute=0),
        cron(run_financial_reporting_monthly, day=1, hour=1, minute=0),
        cron(run_payment_run_weekly, weekday=0, hour=7, minute=0),
        cron(run_budget_check_weekly, weekday=0, hour=7, minute=30),
        cron(fetch_exchange_rates_daily, hour=0, minute=5),
        cron(run_reconciliation_scheduled_check, minute=0),  # hourly
        cron(run_month_end_close_scheduled, hour=0, minute=10),  # daily midnight UTC
        cron(resync_integrations_daily, hour=3, minute=0),   # daily 3am UTC
    ]
    on_startup = startup
    on_shutdown = shutdown

    redis_settings = RedisSettings.from_dsn(get_settings().redis_public_url)

    max_jobs = 10
    job_timeout = 900
    max_tries = 3
