"""
Direct tool dispatch - maps tool type or event type to arq job and enqueues.
No intermediate hop. Called by API routes and the app.events enqueue helper.
"""
from prisma.errors import UniqueViolationError

from app.core.logging import get_logger

logger = get_logger(__name__)

# Maps tool_type (dashboard / API key trigger) → arq job function name
TOOL_TYPE_TO_JOB: dict[str, str] = {
    "invoice_processing":  "run_invoice_job",
    "receipt_processing":  "run_receipt_job",
    "reconciliation":      "run_reconciliation_job",
    "expense_control":     "run_expense_control_job",
    "spend_control":       "run_expense_control_job",
    "accounts_payable":    "run_accounts_payable_job",
    "tax_compliance":      "run_tax_compliance_job",
    "financial_reporting": "run_financial_reporting_job",
    "payment_run":         "run_payment_run_job",
    "document_intelligence": "run_document_intelligence_job",
    "payroll_reconciliation": "run_payroll_rec_job",
}

# Maps event_type (integration sync / webhook) → arq job function name
EVENT_TYPE_TO_JOB: dict[str, str] = {
    "invoice_received":          "run_invoice_received_job",
    "receipt_received":          "run_receipt_received_job",
    "document_received":         "run_document_received_job",
    "reconciliation_run":        "run_reconciliation_job",
    "reconciliation_requested":  "run_reconciliation_job",
    "expense_control_run":       "run_expense_control_job",
    "expense_submitted":         "run_expense_control_job",
    "spend_control_run":         "run_expense_control_job",
    "ap_run":                    "run_accounts_payable_job",
    "tax_compliance_run":        "run_tax_compliance_job",
    "financial_report_run":      "run_financial_reporting_job",
    "payment_run_requested":     "run_payment_run_job",
}

# Maps event_type → tool DB type (used to look up the active tool for execution creation)
EVENT_TYPE_TO_TOOL_TYPE: dict[str, str] = {
    "invoice_received":          "invoice_processing",
    "receipt_received":          "receipt_processing",
    "document_received":         "document_intelligence",
    "reconciliation_run":        "reconciliation",
    "reconciliation_requested":  "reconciliation",
    "expense_control_run":       "expense_control",
    "expense_submitted":         "expense_control",
    "spend_control_run":         "spend_control",
    "ap_run":                    "accounts_payable",
    "tax_compliance_run":        "tax_compliance",
    "financial_report_run":      "financial_reporting",
    "payment_run_requested":     "payment_run",
}


async def enqueue_for_tool_type(
    *,
    pool,
    tool_type: str,
    execution_id: str,
    tenant_id: str,
    tool_id: str,
    payload: dict,
) -> None:
    """Enqueue the correct arq job for a tool_type (dashboard / API key path)."""
    job_name = TOOL_TYPE_TO_JOB.get(tool_type)
    if not job_name:
        logger.warning(
            "unknown_tool_type_for_dispatch",
            extra={"tool_type": tool_type, "execution_id": execution_id},
        )
        return

    kwargs: dict = {
        "execution_id": execution_id,
        "tenant_id": tenant_id,
        "tool_id": tool_id,
    }

    if tool_type == "reconciliation":
        await pool.enqueue_job(
            job_name, **kwargs,
            period_days=payload.get("period_days", 30),
            period_start=payload.get("period_start"),
            period_end=payload.get("period_end"),
            account_ids=payload.get("account_ids"),
            integration_sources=payload.get("integration_sources"),
            policy_overrides=payload.get("policy") if isinstance(payload.get("policy"), dict) else None,
        )
    elif tool_type in ("expense_control", "spend_control"):
        await pool.enqueue_job(
            job_name, **kwargs,
            transaction_ids=payload.get("transaction_ids", []),
        )
    elif tool_type == "document_intelligence":
        await pool.enqueue_job(
            job_name, **kwargs,
            file_bytes=payload.get("file_bytes", b""),
            content_type=payload.get("content_type", "application/pdf"),
            document_id=payload.get("document_id"),
        )
    else:
        await pool.enqueue_job(
            job_name, **kwargs,
            payload=payload,
            policy_config=payload.get("policy_config", {}),
        )


async def enqueue_for_event(
    *,
    pool,
    event_type: str,
    execution_id: str,
    tenant_id: str,
    tool_id: str,
    payload: dict,
) -> None:
    """Enqueue the correct arq job for an event_type (integration / webhook path)."""
    job_name = EVENT_TYPE_TO_JOB.get(event_type)
    if not job_name:
        logger.warning(
            "unknown_event_type_for_dispatch",
            extra={"event_type": event_type, "execution_id": execution_id},
        )
        return

    kwargs: dict = {
        "execution_id": execution_id,
        "tenant_id": tenant_id,
        "tool_id": tool_id,
    }

    if event_type in ("invoice_received", "receipt_received", "document_received"):
        await pool.enqueue_job(job_name, **kwargs, payload=payload)
    elif event_type in ("reconciliation_run", "reconciliation_requested"):
        await pool.enqueue_job(
            job_name, **kwargs,
            period_days=payload.get("period_days", 30),
            period_start=payload.get("period_start"),
            period_end=payload.get("period_end"),
            account_ids=payload.get("account_ids"),
            integration_sources=payload.get("integration_sources"),
            policy_overrides=payload.get("policy") if isinstance(payload.get("policy"), dict) else None,
        )
    elif event_type in ("expense_control_run", "expense_submitted", "spend_control_run"):
        await pool.enqueue_job(
            job_name, **kwargs,
            transaction_ids=payload.get("transaction_ids", []),
        )
    else:
        await pool.enqueue_job(
            job_name, **kwargs,
            payload=payload,
            policy_config=payload.get("policy_config", {}),
        )


async def enqueue_tool_job(
    *,
    db,
    pool,
    tenant_id: str,
    tool_type: str,
    idempotency_key: str,
    payload: dict,
    triggered_by_email: str | None = None,
) -> str | None:
    """
    Find active tool, create Execution, enqueue job directly.
    Returns execution_id or None if no active tool found.
    Idempotent: duplicate idempotency_key returns existing execution_id.
    """
    tool = await db.tool.find_first(
        where={"tenant_id": tenant_id, "type": tool_type, "status": "active"}
    )
    if not tool:
        logger.warning(
            "no_active_tool_for_dispatch",
            extra={"tenant_id": tenant_id, "tool_type": tool_type},
        )
        return None

    try:
        execution = await db.execution.create(data={
            "tenant_id": tenant_id,
            "tool_id": tool.id,
            "input_ref": idempotency_key,
            "decision": "pending",
            "confidence": 0.0,
            "status": "queued",
            **({"triggered_by_email": triggered_by_email} if triggered_by_email else {}),
        })
    except UniqueViolationError:
        existing = await db.execution.find_first(
            where={"tenant_id": tenant_id, "input_ref": idempotency_key}
        )
        logger.info(
            "execution_deduplicated",
            extra={"idempotency_key": idempotency_key, "tool_type": tool_type},
        )
        return existing.id if existing else None

    await enqueue_for_tool_type(
        pool=pool,
        tool_type=tool_type,
        execution_id=execution.id,
        tenant_id=tenant_id,
        tool_id=tool.id,
        payload=payload,
    )

    logger.info(
        "tool_job_enqueued",
        extra={"execution_id": execution.id, "tool_type": tool_type, "tenant_id": tenant_id},
    )
    return execution.id
