"""
Tests for the receipt processing tool (Phase 6).
Mirrors the invoice integration test structure.
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.models.receipt_parse import ParsedReceipt

PARSED_RECEIPT_AUTO = ParsedReceipt(
    merchant="Tesco Extra",
    amount_minor=1250,
    currency="GBP",
    date=None,
    category="meals",
    confidence=0.92,
)

PARSED_RECEIPT_BLOCKED = ParsedReceipt(
    merchant="Unknown Shop",
    amount_minor=500,
    currency="GBP",
    date=None,
    category="other",
    confidence=0.80,
)

COMMON_ARGS = dict(
    tool_id="tool-r1",
    tenant_id="tenant-1",
    execution_id="exec-r1",
    file_bytes=b"fake-image",
    content_type="image/png",
    policy_config={"allowed_categories": ["meals", "travel", "office_supplies"]},
)


def _mock_audit():
    return AsyncMock(return_value="audit-id")


@pytest.mark.asyncio
async def test_receipt_auto_approved():
    with (
        patch("app.tools.receipt_processing._extract_receipt", return_value=PARSED_RECEIPT_AUTO),
        patch("app.tools.receipt_processing.write_audit_log", _mock_audit()),
    ):
        from app.tools.receipt_processing import execute_receipt_tool
        result = await execute_receipt_tool(**COMMON_ARGS)
    assert result["decision"] == "auto_approved"
    assert result["confidence"] == 0.92


@pytest.mark.asyncio
async def test_receipt_blocked_category():
    with (
        patch("app.tools.receipt_processing._extract_receipt", return_value=PARSED_RECEIPT_BLOCKED),
        patch("app.tools.receipt_processing.write_audit_log", _mock_audit()),
    ):
        from app.tools.receipt_processing import execute_receipt_tool
        result = await execute_receipt_tool(**COMMON_ARGS)
    assert result["decision"] == "blocked"
    assert "category" in result["reason"].lower()


@pytest.mark.asyncio
async def test_receipt_audit_written_on_auto():
    mock_audit = _mock_audit()
    with (
        patch("app.tools.receipt_processing._extract_receipt", return_value=PARSED_RECEIPT_AUTO),
        patch("app.tools.receipt_processing.write_audit_log", mock_audit),
    ):
        from app.tools.receipt_processing import execute_receipt_tool
        await execute_receipt_tool(**COMMON_ARGS)
    mock_audit.assert_called_once()


@pytest.mark.asyncio
async def test_receipt_audit_written_on_blocked():
    mock_audit = _mock_audit()
    with (
        patch("app.tools.receipt_processing._extract_receipt", return_value=PARSED_RECEIPT_BLOCKED),
        patch("app.tools.receipt_processing.write_audit_log", mock_audit),
    ):
        from app.tools.receipt_processing import execute_receipt_tool
        await execute_receipt_tool(**COMMON_ARGS)
    mock_audit.assert_called_once()


@pytest.mark.asyncio
async def test_receipt_low_confidence_raises():
    low_conf = PARSED_RECEIPT_AUTO.model_copy(update={"confidence": 0.3})
    with patch("app.tools.receipt_processing._extract_receipt", return_value=low_conf):
        from app.tools.receipt_processing import execute_receipt_tool
        with pytest.raises(ValueError, match="confidence"):
            await execute_receipt_tool(**COMMON_ARGS)


@pytest.mark.asyncio
async def test_receipt_operation_fails_if_audit_fails():
    async def failing_audit(*args, **kwargs):
        raise RuntimeError("Audit log write failed")

    with (
        patch("app.tools.receipt_processing._extract_receipt", return_value=PARSED_RECEIPT_AUTO),
        patch("app.tools.receipt_processing.write_audit_log", failing_audit),
    ):
        from app.tools.receipt_processing import execute_receipt_tool
        with pytest.raises(RuntimeError, match="Audit log write failed"):
            await execute_receipt_tool(**COMMON_ARGS)
