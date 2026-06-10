"""
tests/test_tools.py — Unit tests for tool input validation.

Tests that tools validate their inputs correctly and raise MCPError with
helpful messages — without making any real API calls.
"""
import os
import pytest

from clendan_mcp.auth import MCPError


# ---------------------------------------------------------------------------
# Invoice tool tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_invoice_missing_file(tmp_path):
    from clendan_mcp.tools.invoices import parse_invoice
    with pytest.raises(MCPError, match="File not found"):
        await parse_invoice(str(tmp_path / "nonexistent.pdf"))


@pytest.mark.asyncio
async def test_parse_invoice_wrong_type(tmp_path):
    from clendan_mcp.tools.invoices import parse_invoice
    f = tmp_path / "doc.docx"
    f.write_bytes(b"fake content")
    with pytest.raises(MCPError, match="Unsupported file type"):
        await parse_invoice(str(f))


@pytest.mark.asyncio
async def test_parse_invoice_empty_file(tmp_path):
    from clendan_mcp.tools.invoices import parse_invoice
    f = tmp_path / "empty.pdf"
    f.write_bytes(b"")
    with pytest.raises(MCPError, match="empty"):
        await parse_invoice(str(f))


@pytest.mark.asyncio
async def test_run_invoice_worker_wrong_type():
    from clendan_mcp.tools.invoices import run_invoice_worker
    with pytest.raises(MCPError, match="must be a dict"):
        await run_invoice_worker("not a dict")  # type: ignore


@pytest.mark.asyncio
async def test_run_invoice_worker_empty_dict():
    from clendan_mcp.tools.invoices import run_invoice_worker
    with pytest.raises(MCPError, match="empty"):
        await run_invoice_worker({})


# ---------------------------------------------------------------------------
# Approval tool tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approve_execution_missing_id():
    from clendan_mcp.tools.approvals import approve_execution
    with pytest.raises(MCPError, match="approval_id is required"):
        await approve_execution("")


@pytest.mark.asyncio
async def test_reject_execution_missing_id():
    from clendan_mcp.tools.approvals import reject_execution
    with pytest.raises(MCPError, match="approval_id is required"):
        await reject_execution("", reason="bad invoice")


@pytest.mark.asyncio
async def test_reject_execution_missing_reason():
    from clendan_mcp.tools.approvals import reject_execution
    with pytest.raises(MCPError, match="reason is required"):
        await reject_execution("appr_123", reason="")


@pytest.mark.asyncio
async def test_get_approval_detail_missing_id():
    from clendan_mcp.tools.approvals import get_approval_detail
    with pytest.raises(MCPError, match="approval_id is required"):
        await get_approval_detail("  ")


# ---------------------------------------------------------------------------
# Audit tool tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_audit_trail_invalid_worker_type():
    from clendan_mcp.tools.audit import get_audit_trail
    with pytest.raises(MCPError, match="Invalid worker_type"):
        await get_audit_trail(worker_type="banana_worker")


@pytest.mark.asyncio
async def test_get_audit_trail_invalid_status():
    from clendan_mcp.tools.audit import get_audit_trail
    with pytest.raises(MCPError, match="Invalid status"):
        await get_audit_trail(status="maybe")


@pytest.mark.asyncio
async def test_get_audit_trail_invalid_limit():
    from clendan_mcp.tools.audit import get_audit_trail
    with pytest.raises(MCPError, match="limit must be between"):
        await get_audit_trail(limit=0)


@pytest.mark.asyncio
async def test_get_execution_detail_missing_id():
    from clendan_mcp.tools.audit import get_execution_detail
    with pytest.raises(MCPError, match="trace_id is required"):
        await get_execution_detail("")


# ---------------------------------------------------------------------------
# Worker tool tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_worker_status_invalid_type():
    from clendan_mcp.tools.workers import get_worker_status
    with pytest.raises(MCPError, match="Unknown worker type"):
        await get_worker_status("super_ai_worker")


@pytest.mark.asyncio
async def test_get_policy_rules_invalid_type():
    from clendan_mcp.tools.workers import get_policy_rules
    with pytest.raises(MCPError, match="Unknown worker type"):
        await get_policy_rules("unknown_type")


# ---------------------------------------------------------------------------
# Fraud score tool tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_score_fraud_missing_id():
    from clendan_mcp.tools.api_tools import score_fraud
    with pytest.raises(MCPError, match="transaction_id is required"):
        await score_fraud("", amount_minor=100, currency="GBP",
                         counterparty="Acme", transaction_type="payment")


@pytest.mark.asyncio
async def test_score_fraud_negative_amount():
    from clendan_mcp.tools.api_tools import score_fraud
    with pytest.raises(MCPError, match="non-negative"):
        await score_fraud("tx_1", amount_minor=-1, currency="GBP",
                         counterparty="Acme", transaction_type="payment")


@pytest.mark.asyncio
async def test_score_fraud_bad_currency():
    from clendan_mcp.tools.api_tools import score_fraud
    with pytest.raises(MCPError, match="ISO 4217"):
        await score_fraud("tx_1", amount_minor=100, currency="GBPX",
                         counterparty="Acme", transaction_type="payment")


@pytest.mark.asyncio
async def test_score_fraud_invalid_type():
    from clendan_mcp.tools.api_tools import score_fraud
    with pytest.raises(MCPError, match="Invalid transaction_type"):
        await score_fraud("tx_1", amount_minor=100, currency="GBP",
                         counterparty="Acme", transaction_type="zap")


# ---------------------------------------------------------------------------
# Contract extraction tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_contract_missing_file(tmp_path):
    from clendan_mcp.tools.api_tools import extract_contract_data
    with pytest.raises(MCPError, match="File not found"):
        await extract_contract_data(str(tmp_path / "missing.pdf"))


@pytest.mark.asyncio
async def test_extract_contract_wrong_type(tmp_path):
    from clendan_mcp.tools.api_tools import extract_contract_data
    f = tmp_path / "contract.docx"
    f.write_bytes(b"fake content")
    with pytest.raises(MCPError, match="only supports PDF"):
        await extract_contract_data(str(f))


# ---------------------------------------------------------------------------
# Reconcile tool tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reconcile_both_empty():
    from clendan_mcp.tools.api_tools import reconcile_datasets
    with pytest.raises(MCPError, match="empty"):
        await reconcile_datasets([], [], "2024-01-01", "2024-01-31")


@pytest.mark.asyncio
async def test_reconcile_period_reversed():
    from clendan_mcp.tools.api_tools import reconcile_datasets
    with pytest.raises(MCPError, match="period_end must be"):
        await reconcile_datasets(
            [{"id": "1"}], [{"id": "2"}],
            "2024-02-01", "2024-01-01"
        )


# ---------------------------------------------------------------------------
# Integration tool tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_integration_status_invalid_type():
    from clendan_mcp.tools.integrations import get_integration_status
    with pytest.raises(MCPError, match="Unknown integration type"):
        await get_integration_status("mybank")


@pytest.mark.asyncio
async def test_trigger_sync_invalid_type():
    from clendan_mcp.tools.integrations import trigger_sync
    with pytest.raises(MCPError, match="Unknown integration type"):
        await trigger_sync("randombank")


# ---------------------------------------------------------------------------
# Analytics tool tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_execution_stats_invalid_period():
    from clendan_mcp.tools.analytics import get_execution_stats
    with pytest.raises(MCPError, match="Invalid period"):
        await get_execution_stats("365d")


@pytest.mark.asyncio
async def test_get_hours_saved_invalid_period():
    from clendan_mcp.tools.analytics import get_hours_saved
    with pytest.raises(MCPError, match="Invalid period"):
        await get_hours_saved("2y")
