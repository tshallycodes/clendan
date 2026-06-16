"""
Unit tests for execute_invoice_tool business logic.
Claude and DB calls are mocked — no external connections required.
"""
import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.invoice_parse import ParsedInvoice, LineItem


def _make_parsed_invoice(**overrides) -> ParsedInvoice:
    defaults = dict(
        vendor="Acme Corp",
        invoice_number="INV-001",
        line_items=[LineItem(description="Service", quantity=1, unit_price_minor=10_000, total_minor=10_000)],
        amount_minor=10_000,
        currency="GBP",
        due_date=date.today(),
        vat_minor=None,
        po_number=None,
        confidence=0.95,
    )
    defaults.update(overrides)
    return ParsedInvoice(**defaults)


POLICY_CONFIG = {
    "verified_suppliers": ["Acme Corp"],
    "allowed_currencies": ["GBP", "USD", "EUR"],
    "auto_threshold_minor": 50_000,
    "block_threshold_minor": 1_000_000,
    "min_ocr_confidence": 0.85,
    "duplicate_window_days": 90,
    "max_invoice_age_days": 180,
    "approval_tier_1_minor": 100_000,
    "approval_tier_2_minor": 500_000,
}


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.invoice.find_first = AsyncMock(return_value=None)  # no duplicate by default
    return db


@pytest.fixture
def mock_audit():
    return AsyncMock(return_value="audit_id_123")


class TestExecuteInvoiceTool:

    @pytest.mark.asyncio
    async def test_auto_approved_when_all_rules_pass(self, mock_db, mock_audit):
        parsed = _make_parsed_invoice()

        with (
            patch("app.tools.invoice_processing._extract_invoice", AsyncMock(return_value=parsed)),
            patch("app.tools.invoice_processing.get_db", return_value=mock_db),
            patch("app.tools.invoice_processing.write_audit_log", mock_audit),
        ):
            from app.tools.invoice_processing import execute_invoice_tool
            result = await execute_invoice_tool(
                tool_id="w1", tenant_id="t1", execution_id="e1",
                file_bytes=b"fake", content_type="image/png",
                policy_config=POLICY_CONFIG,
            )

        assert result["decision"] == "auto_approved"
        mock_audit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_approval_required_when_amount_exceeds_threshold(self, mock_db, mock_audit):
        parsed = _make_parsed_invoice(amount_minor=75_000)

        with (
            patch("app.tools.invoice_processing._extract_invoice", AsyncMock(return_value=parsed)),
            patch("app.tools.invoice_processing.get_db", return_value=mock_db),
            patch("app.tools.invoice_processing.write_audit_log", mock_audit),
        ):
            from app.tools.invoice_processing import execute_invoice_tool
            result = await execute_invoice_tool(
                tool_id="w1", tenant_id="t1", execution_id="e1",
                file_bytes=b"fake", content_type="image/png",
                policy_config=POLICY_CONFIG,
            )

        assert result["decision"] == "approval_required"

    @pytest.mark.asyncio
    async def test_blocked_when_ocr_confidence_too_low(self, mock_db, mock_audit):
        parsed = _make_parsed_invoice(confidence=0.60)

        with (
            patch("app.tools.invoice_processing._extract_invoice", AsyncMock(return_value=parsed)),
            patch("app.tools.invoice_processing.get_db", return_value=mock_db),
            patch("app.tools.invoice_processing.write_audit_log", mock_audit),
        ):
            from app.tools.invoice_processing import execute_invoice_tool
            result = await execute_invoice_tool(
                tool_id="w1", tenant_id="t1", execution_id="e1",
                file_bytes=b"fake", content_type="image/png",
                policy_config=POLICY_CONFIG,
            )

        assert result["decision"] == "blocked"
        assert result["rule_triggered"] == "ocr_confidence"

    @pytest.mark.asyncio
    async def test_blocked_on_duplicate_invoice(self, mock_audit):
        parsed = _make_parsed_invoice()
        existing = MagicMock()  # simulate existing invoice in DB

        db = MagicMock()
        db.invoice.find_first = AsyncMock(return_value=existing)

        with (
            patch("app.tools.invoice_processing._extract_invoice", AsyncMock(return_value=parsed)),
            patch("app.tools.invoice_processing.get_db", return_value=db),
            patch("app.tools.invoice_processing.write_audit_log", mock_audit),
        ):
            from app.tools.invoice_processing import execute_invoice_tool
            result = await execute_invoice_tool(
                tool_id="w1", tenant_id="t1", execution_id="e1",
                file_bytes=b"fake", content_type="image/png",
                policy_config=POLICY_CONFIG,
            )

        assert result["decision"] == "blocked"
        assert result["rule_triggered"] == "duplicate_invoice"

    @pytest.mark.asyncio
    async def test_audit_written_before_return(self, mock_db, mock_audit):
        """Audit must always be written, even for blocked decisions."""
        parsed = _make_parsed_invoice(currency="JPY")  # will be blocked

        with (
            patch("app.tools.invoice_processing._extract_invoice", AsyncMock(return_value=parsed)),
            patch("app.tools.invoice_processing.get_db", return_value=mock_db),
            patch("app.tools.invoice_processing.write_audit_log", mock_audit),
        ):
            from app.tools.invoice_processing import execute_invoice_tool
            result = await execute_invoice_tool(
                tool_id="w1", tenant_id="t1", execution_id="e1",
                file_bytes=b"fake", content_type="image/png",
                policy_config=POLICY_CONFIG,
            )

        assert result["decision"] == "blocked"
        mock_audit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_tiered_approval_for_large_amount(self, mock_db, mock_audit):
        parsed = _make_parsed_invoice(amount_minor=200_000)

        with (
            patch("app.tools.invoice_processing._extract_invoice", AsyncMock(return_value=parsed)),
            patch("app.tools.invoice_processing.get_db", return_value=mock_db),
            patch("app.tools.invoice_processing.write_audit_log", mock_audit),
        ):
            from app.tools.invoice_processing import execute_invoice_tool
            result = await execute_invoice_tool(
                tool_id="w1", tenant_id="t1", execution_id="e1",
                file_bytes=b"fake", content_type="image/png",
                policy_config=POLICY_CONFIG,
            )

        assert result["decision"] == "approval_required"
        assert result["rule_triggered"] in ("approval_tier_1", "approval_tier_2", "amount_approve_threshold")

    @pytest.mark.asyncio
    async def test_extract_failure_propagates(self, mock_db, mock_audit):
        with (
            patch("app.tools.invoice_processing._extract_invoice",
                  AsyncMock(side_effect=ValueError("Claude returned unparseable response"))),
            patch("app.tools.invoice_processing.get_db", return_value=mock_db),
            patch("app.tools.invoice_processing.write_audit_log", mock_audit),
        ):
            from app.tools.invoice_processing import execute_invoice_tool
            with pytest.raises(ValueError, match="unparseable"):
                await execute_invoice_tool(
                    tool_id="w1", tenant_id="t1", execution_id="e1",
                    file_bytes=b"fake", content_type="image/png",
                    policy_config=POLICY_CONFIG,
                )

        mock_audit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_audit_failure_raises(self, mock_db):
        parsed = _make_parsed_invoice()
        failing_audit = AsyncMock(side_effect=RuntimeError("Audit log write failed"))

        with (
            patch("app.tools.invoice_processing._extract_invoice", AsyncMock(return_value=parsed)),
            patch("app.tools.invoice_processing.get_db", return_value=mock_db),
            patch("app.tools.invoice_processing.write_audit_log", failing_audit),
        ):
            from app.tools.invoice_processing import execute_invoice_tool
            with pytest.raises(RuntimeError, match="Audit log write failed"):
                await execute_invoice_tool(
                    tool_id="w1", tenant_id="t1", execution_id="e1",
                    file_bytes=b"fake", content_type="image/png",
                    policy_config=POLICY_CONFIG,
                )


class TestCheckDuplicate:

    @pytest.mark.asyncio
    async def test_returns_true_when_duplicate_exists(self):
        db = MagicMock()
        db.invoice.find_first = AsyncMock(return_value=MagicMock())

        with patch("app.tools.invoice_processing.get_db", return_value=db):
            from app.tools.invoice_processing import _check_duplicate
            result = await _check_duplicate("tenant1", "INV-001", 90)

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_no_duplicate(self):
        db = MagicMock()
        db.invoice.find_first = AsyncMock(return_value=None)

        with patch("app.tools.invoice_processing.get_db", return_value=db):
            from app.tools.invoice_processing import _check_duplicate
            result = await _check_duplicate("tenant1", "INV-999", 90)

        assert result is False

    @pytest.mark.asyncio
    async def test_scopes_to_tenant(self):
        db = MagicMock()
        db.invoice.find_first = AsyncMock(return_value=None)

        with patch("app.tools.invoice_processing.get_db", return_value=db):
            from app.tools.invoice_processing import _check_duplicate
            await _check_duplicate("tenant_abc", "INV-001", 90)

        where = db.invoice.find_first.call_args[1]["where"]
        assert where["tenant_id"] == "tenant_abc"
        assert where["invoice_number"] == "INV-001"
