"""
Tests for the document_intelligence tool.

Covers policy parsing, analysis output shaping, and the full arq job logic:
classification-error handling, confidence-threshold decisions, keyword flagging,
audit-before-complete ordering, and the policy_config kwarg contract used by the
document_received auto-ingest path (run_document_received_job).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---- pure helpers -----------------------------------------------------------

def test_parse_policy_defaults():
    from app.tools.document_intelligence import _parse_policy
    policy = _parse_policy({})
    assert policy.auto_approve_confidence_min == 0.80
    assert policy.flag_keywords == ""


def test_parse_policy_maps_percentage_confidence():
    from app.tools.document_intelligence import _parse_policy
    policy = _parse_policy({"auto_approve_confidence_min": 90, "flag_keywords": "lawsuit, penalty"})
    assert policy.auto_approve_confidence_min == 0.90
    assert policy.flag_keywords == "lawsuit, penalty"


@pytest.mark.asyncio
async def test_process_document_shapes_output():
    analysis = {
        "document_subtype": "contract",
        "summary": "A supply contract.",
        "risks": ["r1"], "loopholes": ["l1"], "improvements": ["i1"],
        "parties": ["Acme Ltd"], "key_dates": ["2026-01-01: start"],
        "confidence": 0.88,
    }
    with patch("app.tools.document_intelligence._call_claude_vision", AsyncMock(return_value=analysis)):
        from app.tools.document_intelligence import _process_document
        result = await _process_document(b"pdf-bytes", "application/pdf")
    assert result["decision"] == "analysed"
    assert result["confidence"] == 0.88
    assert result["extracted"]["document_subtype"] == "contract"
    assert result["extracted"]["risks"] == ["r1"]
    assert result["extracted"]["parties"] == ["Acme Ltd"]


# ---- job logic --------------------------------------------------------------

def _mock_db(config_json: dict | None = None):
    db = MagicMock()
    db.tool = MagicMock()
    db.tool.find_first = AsyncMock(return_value=MagicMock(config_json=config_json or {}))
    db.document = MagicMock()
    db.document.update = AsyncMock(return_value=None)
    db.execution = MagicMock()
    db.execution.update = AsyncMock(return_value=None)
    return db


def _analysis(confidence: float, extracted: dict | None = None) -> dict:
    return {
        "decision": "analysed",
        "confidence": confidence,
        "reason": "Document analysed — contract",
        "extracted": extracted if extracted is not None else {"summary": "x", "risks": []},
    }


def _patches(db, audit, complete, classify_ret, process_ret, dlq=None):
    process_mock = AsyncMock(return_value=process_ret) if process_ret is not None else AsyncMock()
    return (
        patch("app.tools.document_intelligence.get_db", return_value=db),
        patch("app.tools.document_intelligence.write_audit_log", audit),
        patch("app.tools.document_intelligence.complete_execution", complete),
        patch("app.tools.document_intelligence.push_to_dlq", dlq or AsyncMock()),
        patch("app.tools.document_intelligence._classify_document", AsyncMock(return_value=classify_ret)),
        patch("app.tools.document_intelligence._process_document", process_mock),
    ), process_mock


@pytest.mark.asyncio
async def test_job_auto_approved_high_confidence():
    db = _mock_db()
    audit = AsyncMock(return_value="audit-id")
    complete = AsyncMock(return_value="auto_approved")
    ps, _ = _patches(db, audit, complete, {"type": "document"}, _analysis(0.95))
    with ps[0], ps[1], ps[2], ps[3], ps[4], ps[5]:
        from app.tools.document_intelligence import run_document_intelligence_job
        result = await run_document_intelligence_job(
            {}, execution_id="e1", tenant_id="t1", tool_id="tool1",
            file_bytes=b"pdf", content_type="application/pdf", document_id="d1",
        )
    assert result["decision"] == "auto_approved"
    assert result["document_type"] == "document"
    audit.assert_called_once()
    complete.assert_called_once()
    assert complete.call_args.kwargs["decision"] == "auto_approved"
    assert complete.call_args.kwargs["confidence"] == 0.95


@pytest.mark.asyncio
async def test_job_approval_required_low_confidence():
    db = _mock_db()
    audit = AsyncMock(return_value="audit-id")
    complete = AsyncMock(return_value="approval_required")
    ps, _ = _patches(db, audit, complete, {"type": "document"}, _analysis(0.50))
    with ps[0], ps[1], ps[2], ps[3], ps[4], ps[5]:
        from app.tools.document_intelligence import run_document_intelligence_job
        result = await run_document_intelligence_job(
            {}, execution_id="e2", tenant_id="t1", tool_id="tool1",
            file_bytes=b"pdf", content_type="application/pdf", document_id="d2",
        )
    assert result["decision"] == "approval_required"


@pytest.mark.asyncio
async def test_job_keyword_flag_forces_approval_even_when_confident():
    db = _mock_db(config_json={"flag_keywords": "lawsuit"})
    audit = AsyncMock(return_value="audit-id")
    complete = AsyncMock(return_value="approval_required")
    analysis = _analysis(0.99, {"risks": ["Possible lawsuit exposure"]})
    ps, _ = _patches(db, audit, complete, {"type": "document"}, analysis)
    with ps[0], ps[1], ps[2], ps[3], ps[4], ps[5]:
        from app.tools.document_intelligence import run_document_intelligence_job
        result = await run_document_intelligence_job(
            {}, execution_id="e3", tenant_id="t1", tool_id="tool1",
            file_bytes=b"pdf", content_type="application/pdf", document_id="d3",
        )
    assert result["decision"] == "approval_required"
    # rule_triggered flows into the audit reasoning trace
    trace = audit.call_args.kwargs["reasoning_trace"]
    assert trace["rule_triggered"] == "keyword: lawsuit"


@pytest.mark.asyncio
async def test_job_classification_error_marks_pending_unreadable():
    db = _mock_db()
    audit = AsyncMock(return_value="audit-id")
    complete = AsyncMock(return_value="classification_failed")
    ps, process_mock = _patches(
        db, audit, complete,
        {"type": "error", "error_message": "Image Unreadable"},
        None,
    )
    with ps[0], ps[1], ps[2], ps[3], ps[4], ps[5]:
        from app.tools.document_intelligence import run_document_intelligence_job
        result = await run_document_intelligence_job(
            {}, execution_id="e4", tenant_id="t1", tool_id="tool1",
            file_bytes=b"pdf", content_type="application/pdf", document_id="d4",
        )
    assert result["document_type"] == "pending"
    assert result["decision"] == "classification_failed"
    assert result["confidence"] == 0.0
    assert result["reason"] == "Image Unreadable"
    process_mock.assert_not_called()  # analysis skipped on classification error


@pytest.mark.asyncio
async def test_job_accepts_policy_config_kwarg_and_skips_db_read():
    """Regression: run_document_received_job enqueues the job WITH policy_config.

    The job must accept the kwarg (else arq raises TypeError at bind time, outside the
    try/except, stranding the execution) and use it in place of a tenant DB read.
    """
    db = _mock_db()
    db.tool.find_first = AsyncMock(side_effect=AssertionError("must not read tool when policy_config is given"))
    audit = AsyncMock(return_value="audit-id")
    complete = AsyncMock(return_value="auto_approved")
    ps, _ = _patches(db, audit, complete, {"type": "document"}, _analysis(0.95))
    with ps[0], ps[1], ps[2], ps[3], ps[4], ps[5]:
        from app.tools.document_intelligence import run_document_intelligence_job
        result = await run_document_intelligence_job(
            {}, execution_id="e5", tenant_id="t1", tool_id="tool1",
            file_bytes=b"pdf", content_type="application/pdf", document_id="d5",
            policy_config={"auto_approve_confidence_min": 50},
        )
    assert result["decision"] == "auto_approved"
    db.tool.find_first.assert_not_called()


@pytest.mark.asyncio
async def test_job_audit_failure_aborts_before_complete_execution():
    """Audit must be written before the execution is finalised — if audit fails the
    operation fails and complete_execution is never reached."""
    db = _mock_db()
    audit = AsyncMock(side_effect=RuntimeError("audit log down"))
    complete = AsyncMock(return_value="auto_approved")
    ps, _ = _patches(db, audit, complete, {"type": "document"}, _analysis(0.95))
    with ps[0], ps[1], ps[2], ps[3], ps[4], ps[5]:
        from app.tools.document_intelligence import run_document_intelligence_job
        with pytest.raises(RuntimeError, match="audit log down"):
            await run_document_intelligence_job(
                {}, execution_id="e6", tenant_id="t1", tool_id="tool1",
                file_bytes=b"pdf", content_type="application/pdf", document_id="d6",
            )
    complete.assert_not_called()
    # execution marked failed on the error path
    db.execution.update.assert_awaited()
