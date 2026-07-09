"""
Tests for the Invoice & Receipt Processing tool (internal type document_intelligence).

Covers classification routing - invoice -> AP (execute_invoice_tool + native Invoice),
receipt -> expense (execute_receipt_tool), other -> no action - plus audit-before-complete
ordering and the policy_config auto-ingest contract.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _mock_db(config_json: dict | None = None):
    db = MagicMock()
    db.tool.find_first = AsyncMock(return_value=MagicMock(config_json=config_json or {}))
    db.document.update = AsyncMock(return_value=None)
    db.execution.update = AsyncMock(return_value=None)
    db.invoice.create = AsyncMock(return_value=None)
    db.accountingexpense.find_first = AsyncMock(return_value=None)
    db.accountingexpense.create = AsyncMock(return_value=None)
    return db


def _patches(db, audit, complete, classify_ret):
    return (
        patch("app.tools.document_intelligence.get_db", return_value=db),
        patch("app.tools.document_intelligence.write_audit_log", audit),
        patch("app.tools.document_intelligence.complete_execution", complete),
        patch("app.tools.document_intelligence.push_to_dlq", AsyncMock()),
        patch("app.tools.document_intelligence._classify_document", AsyncMock(return_value=classify_ret)),
    )


@pytest.mark.asyncio
async def test_invoice_routes_to_ap_and_creates_native_invoice():
    db = _mock_db()
    audit = AsyncMock(return_value="audit-id")
    complete = AsyncMock(return_value="auto_approved")
    inv_result = {
        "decision": "auto_approved", "reason": "within thresholds", "rule_triggered": None,
        "parsed_invoice": {
            "vendor": "Acme Ltd", "invoice_number": "INV-1", "amount_minor": 12345,
            "currency": "GBP", "due_date": "2026-06-30", "line_items": [],
        },
        "confidence": 0.97,
    }
    execute_invoice = AsyncMock(return_value=inv_result)
    ps = _patches(db, audit, complete, {"type": "invoice"})
    with ps[0], ps[1], ps[2], ps[3], ps[4], patch(
        "app.tools.invoice_processing.execute_invoice_tool", execute_invoice
    ):
        from app.tools.document_intelligence import run_document_intelligence_job
        result = await run_document_intelligence_job(
            {}, execution_id="e1", tenant_id="t1", tool_id="tool1",
            file_bytes=b"pdf", content_type="application/pdf", document_id="d1",
        )
    assert result["document_type"] == "invoice"
    assert result["decision"] == "auto_approved"
    execute_invoice.assert_awaited_once()
    db.invoice.create.assert_awaited_once()
    assert db.invoice.create.await_args.kwargs["data"]["vendor"] == "Acme Ltd"
    audit.assert_not_called()  # invoice audits itself inside execute_invoice_tool
    complete.assert_awaited_once()


@pytest.mark.asyncio
async def test_receipt_routes_to_expense():
    db = _mock_db()
    audit = AsyncMock(return_value="audit-id")
    complete = AsyncMock(return_value="auto_approved")
    rec_result = {
        "decision": "auto_approved", "reason": "ok",
        "parsed_receipt": {"merchant": "Cafe", "amount_minor": 500, "category": "meals", "currency": "GBP"},
        "confidence": 0.95,
    }
    execute_receipt = AsyncMock(return_value=rec_result)
    ps = _patches(db, audit, complete, {"type": "receipt"})
    with ps[0], ps[1], ps[2], ps[3], ps[4], patch(
        "app.tools.receipt_processing.execute_receipt_tool", execute_receipt
    ):
        from app.tools.document_intelligence import run_document_intelligence_job
        result = await run_document_intelligence_job(
            {}, execution_id="e2", tenant_id="t1", tool_id="tool1",
            file_bytes=b"pdf", content_type="application/pdf", document_id="d2",
        )
    assert result["document_type"] == "receipt"
    assert result["decision"] == "auto_approved"
    execute_receipt.assert_awaited_once()
    audit.assert_not_called()  # receipt audits itself
    complete.assert_awaited_once()
    # receipt becomes a native expense Spend Control will assess
    db.accountingexpense.create.assert_awaited_once()
    exp = db.accountingexpense.create.await_args.kwargs["data"]
    assert exp["source"] == "receipt"
    assert exp["amount_cents"] == 500
    assert exp["contact_name"] == "Cafe"
    assert exp["approved"] is False


@pytest.mark.asyncio
async def test_other_document_no_action():
    db = _mock_db()
    audit = AsyncMock(return_value="audit-id")
    complete = AsyncMock(return_value="no_action")
    ps = _patches(db, audit, complete, {"type": "other"})
    with ps[0], ps[1], ps[2], ps[3], ps[4]:
        from app.tools.document_intelligence import run_document_intelligence_job
        result = await run_document_intelligence_job(
            {}, execution_id="e3", tenant_id="t1", tool_id="tool1",
            file_bytes=b"pdf", content_type="application/pdf", document_id="d3",
        )
    assert result["document_type"] == "other"
    assert result["decision"] == "no_action"
    assert "no financial action" in result["reason"].lower()
    audit.assert_called_once()  # non-financial doc is still recorded/audited
    complete.assert_awaited_once()


@pytest.mark.asyncio
async def test_classification_error_marks_pending():
    db = _mock_db()
    audit = AsyncMock(return_value="audit-id")
    complete = AsyncMock(return_value="classification_failed")
    ps = _patches(db, audit, complete, {"type": "error", "error_message": "Image Unreadable"})
    with ps[0], ps[1], ps[2], ps[3], ps[4]:
        from app.tools.document_intelligence import run_document_intelligence_job
        result = await run_document_intelligence_job(
            {}, execution_id="e4", tenant_id="t1", tool_id="tool1",
            file_bytes=b"pdf", content_type="application/pdf", document_id="d4",
        )
    assert result["document_type"] == "pending"
    assert result["decision"] == "classification_failed"
    assert result["reason"] == "Image Unreadable"


@pytest.mark.asyncio
async def test_accepts_policy_config_kwarg_and_skips_db_read():
    """The auto-ingest path passes policy_config; the job must accept it and not read the
    tool from the DB (the kwarg is bound before the try/except)."""
    db = _mock_db()
    db.tool.find_first = AsyncMock(side_effect=AssertionError("must not read tool when policy_config given"))
    audit = AsyncMock(return_value="audit-id")
    complete = AsyncMock(return_value="auto_approved")
    execute_invoice = AsyncMock(return_value={
        "decision": "auto_approved", "reason": "ok", "rule_triggered": None,
        "parsed_invoice": {"vendor": "X", "invoice_number": "1", "amount_minor": 1,
                           "currency": "GBP", "line_items": []},
        "confidence": 0.9,
    })
    ps = _patches(db, audit, complete, {"type": "invoice"})
    with ps[0], ps[1], ps[2], ps[3], ps[4], patch(
        "app.tools.invoice_processing.execute_invoice_tool", execute_invoice
    ):
        from app.tools.document_intelligence import run_document_intelligence_job
        result = await run_document_intelligence_job(
            {}, execution_id="e5", tenant_id="t1", tool_id="tool1",
            file_bytes=b"pdf", content_type="application/pdf", document_id="d5",
            policy_config={"auto_threshold_minor": 5000},
        )
    assert result["decision"] == "auto_approved"
    db.tool.find_first.assert_not_called()


def test_spend_control_run_routes_to_accounts_payable():
    """AP workflow chain must assess the bill, not employee expenses."""
    from app.core.dispatch import EVENT_TYPE_TO_JOB, EVENT_TYPE_TO_TOOL_TYPE
    assert EVENT_TYPE_TO_JOB["spend_control_run"] == "run_accounts_payable_job"
    assert EVENT_TYPE_TO_TOOL_TYPE["spend_control_run"] == "spend_control"


@pytest.mark.asyncio
async def test_audit_failure_aborts_before_complete_execution():
    """Audit must be written before the execution is finalised - if audit fails the
    operation fails and complete_execution is never reached."""
    db = _mock_db()
    audit = AsyncMock(side_effect=RuntimeError("audit log down"))
    complete = AsyncMock(return_value="no_action")
    ps = _patches(db, audit, complete, {"type": "other"})
    with ps[0], ps[1], ps[2], ps[3], ps[4]:
        from app.tools.document_intelligence import run_document_intelligence_job
        with pytest.raises(RuntimeError, match="audit log down"):
            await run_document_intelligence_job(
                {}, execution_id="e6", tenant_id="t1", tool_id="tool1",
                file_bytes=b"pdf", content_type="application/pdf", document_id="d6",
            )
    complete.assert_not_called()
    db.execution.update.assert_awaited()
