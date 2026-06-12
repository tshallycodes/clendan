"""
Integration tests for the invoice processing tool.

These tests call execute_invoice_tool directly (bypassing the arq queue)
to verify the full decision flow end-to-end with all dependencies mocked.

1.8 coverage:
- Auto-approved execution end-to-end
- Approval-required execution end-to-end
- Blocked execution end-to-end
- Proof: blocked case → no accounting write occurred
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from app.models.invoice_parse import ParsedInvoice


PARSED_INVOICE_AUTO = ParsedInvoice(
    vendor="Acme Corp",
    invoice_number="INV-001",
    line_items=[],
    amount_minor=10_000,   # £100 — below auto threshold (£500)
    currency="GBP",
    confidence=0.95,
)

PARSED_INVOICE_APPROVE = ParsedInvoice(
    vendor="Unknown Vendor",  # not in verified suppliers → approval required
    invoice_number="INV-002",
    line_items=[],
    amount_minor=10_000,
    currency="GBP",
    confidence=0.90,
)

PARSED_INVOICE_BLOCKED = ParsedInvoice(
    vendor="Acme Corp",
    invoice_number="INV-003",
    line_items=[],
    amount_minor=2_000_000,  # £20,000 — above block threshold (£10,000)
    currency="GBP",
    confidence=0.85,
)

POLICY_CONFIG = {
    "verified_suppliers": ["Acme Corp"],
    "allowed_currencies": ["GBP", "USD", "EUR"],
    "auto_threshold_minor": 50_000,
    "block_threshold_minor": 1_000_000,
}

COMMON_ARGS = dict(
    tool_id="tool-1",
    tenant_id="tenant-1",
    execution_id="exec-1",
    file_bytes=b"fake-image-bytes",
    content_type="image/png",
    policy_config=POLICY_CONFIG,
)


def _mock_audit():
    return AsyncMock(return_value="audit-log-id")


@pytest.mark.asyncio
async def test_auto_approved_end_to_end():
    mock_accounting = AsyncMock()

    with (
        patch("app.tools.invoice_processing._extract_invoice", return_value=PARSED_INVOICE_AUTO),
        patch("app.tools.invoice_processing._mock_accounting_write", mock_accounting),
        patch("app.tools.invoice_processing.write_audit_log", _mock_audit()),
    ):
        from app.tools.invoice_processing import execute_invoice_tool
        result = await execute_invoice_tool(**COMMON_ARGS)

    assert result["decision"] == "auto_approved"
    assert result["confidence"] == 0.95
    mock_accounting.assert_called_once()  # accounting write must occur


@pytest.mark.asyncio
async def test_approval_required_end_to_end():
    mock_accounting = AsyncMock()

    with (
        patch("app.tools.invoice_processing._extract_invoice", return_value=PARSED_INVOICE_APPROVE),
        patch("app.tools.invoice_processing._mock_accounting_write", mock_accounting),
        patch("app.tools.invoice_processing.write_audit_log", _mock_audit()),
    ):
        from app.tools.invoice_processing import execute_invoice_tool
        result = await execute_invoice_tool(**COMMON_ARGS)

    assert result["decision"] == "approval_required"
    mock_accounting.assert_not_called()  # no accounting write for pending approval


@pytest.mark.asyncio
async def test_blocked_end_to_end():
    mock_accounting = AsyncMock()

    with (
        patch("app.tools.invoice_processing._extract_invoice", return_value=PARSED_INVOICE_BLOCKED),
        patch("app.tools.invoice_processing._mock_accounting_write", mock_accounting),
        patch("app.tools.invoice_processing.write_audit_log", _mock_audit()),
    ):
        from app.tools.invoice_processing import execute_invoice_tool
        result = await execute_invoice_tool(**COMMON_ARGS)

    assert result["decision"] == "blocked"


@pytest.mark.asyncio
async def test_blocked_no_accounting_write_proof():
    """
    Proof requirement from 1.8: blocked case must never trigger an accounting write.
    """
    mock_accounting = AsyncMock()

    with (
        patch("app.tools.invoice_processing._extract_invoice", return_value=PARSED_INVOICE_BLOCKED),
        patch("app.tools.invoice_processing._mock_accounting_write", mock_accounting),
        patch("app.tools.invoice_processing.write_audit_log", _mock_audit()),
    ):
        from app.tools.invoice_processing import execute_invoice_tool
        await execute_invoice_tool(**COMMON_ARGS)

    mock_accounting.assert_not_called()


@pytest.mark.asyncio
async def test_audit_written_before_accounting_write():
    """Audit log must be written before any external action (CLAUDE.md requirement)."""
    call_order = []

    async def mock_audit(*args, **kwargs):
        call_order.append("audit")
        return "audit-id"

    async def mock_accounting(*args, **kwargs):
        call_order.append("accounting")

    with (
        patch("app.tools.invoice_processing._extract_invoice", return_value=PARSED_INVOICE_AUTO),
        patch("app.tools.invoice_processing._mock_accounting_write", mock_accounting),
        patch("app.tools.invoice_processing.write_audit_log", mock_audit),
    ):
        from app.tools.invoice_processing import execute_invoice_tool
        await execute_invoice_tool(**COMMON_ARGS)

    assert call_order == ["audit", "accounting"], (
        f"Expected audit before accounting, got: {call_order}"
    )


@pytest.mark.asyncio
async def test_operation_fails_if_audit_write_fails():
    """If audit write fails, the whole operation must fail — no silent success."""
    async def failing_audit(*args, **kwargs):
        raise RuntimeError("Audit log write failed — operation cannot complete")

    mock_accounting = AsyncMock()

    with (
        patch("app.tools.invoice_processing._extract_invoice", return_value=PARSED_INVOICE_AUTO),
        patch("app.tools.invoice_processing._mock_accounting_write", mock_accounting),
        patch("app.tools.invoice_processing.write_audit_log", failing_audit),
    ):
        from app.tools.invoice_processing import execute_invoice_tool
        with pytest.raises(RuntimeError, match="Audit log write failed"):
            await execute_invoice_tool(**COMMON_ARGS)

    mock_accounting.assert_not_called()


@pytest.mark.asyncio
async def test_low_confidence_raises_error():
    low_confidence_invoice = PARSED_INVOICE_AUTO.model_copy(update={"confidence": 0.3})

    with patch("app.tools.invoice_processing._extract_invoice", return_value=low_confidence_invoice):
        from app.tools.invoice_processing import execute_invoice_tool
        with pytest.raises(ValueError, match="confidence"):
            await execute_invoice_tool(**COMMON_ARGS)
