"""
Tool stub smoke tests — Phase 1.
Verifies that all four new tools instantiate, accept minimal valid input,
and return a correctly shaped ToolOutput without touching any external API.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.tools.base import ToolOutput


_RECON_RESULT = {
    "decision": "auto_approved",
    "confidence": 0.9,
    "reasoning": "test",
    "actions_taken": [],
    "output_data": {},
}

_EXPENSE_RESULT = {
    "decision": "auto_approved",
    "confidence": 0.85,
    "reasoning": "test",
    "actions_taken": [],
    "output_data": {},
}

_COLLECTIONS_RESULT = {
    "decision": "auto_approved",
    "confidence": 0.8,
    "reasoning": "test",
    "actions_taken": [],
}

_FRAUD_RESULT = {
    "decision": "auto_approved",
    "confidence": 0.95,
    "reasoning": "test",
    "actions_taken": [],
    "output_data": {},
}


# ---------------------------------------------------------------------------
# ReconciliationTool
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reconciliation_tool_returns_tool_output():
    from app.tools.reconciliation import ReconciliationTool

    tool = ReconciliationTool()
    with patch("app.tools.reconciliation._execute_reconciliation", AsyncMock(return_value=_RECON_RESULT)):
        result = await tool.execute(
            input_data={
                "execution_id": "exec_001",
                "tool_id": "tool_001",
                "source_dataset": [],
                "target_dataset": [],
                "period_start": date(2025, 1, 1),
                "period_end": date(2025, 1, 31),
            },
            tenant_id="tenant_001",
        )

    assert isinstance(result, ToolOutput)
    assert isinstance(result.confidence, float)
    assert 0.0 <= result.confidence <= 1.0
    assert isinstance(result.reasoning, str) and result.reasoning
    assert isinstance(result.actions_taken, list)


# ---------------------------------------------------------------------------
# ExpenseControlTool
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expense_control_tool_returns_tool_output():
    from app.tools.expense_control import ExpenseControlTool

    tool = ExpenseControlTool()
    with patch("app.tools.expense_control._execute_expense_control", AsyncMock(return_value=_EXPENSE_RESULT)):
        result = await tool.execute(
            input_data={
                "execution_id": "exec_001",
                "tool_id": "tool_001",
                "expense_claim_id": "claim_001",
                "amount_minor": 5000,
                "currency": "GBP",
                "category": "travel",
                "receipt_document_ref": "ref_001",
                "submitted_by": "user_001",
                "policy_rules": {},
            },
            tenant_id="tenant_001",
        )

    assert isinstance(result, ToolOutput)
    assert isinstance(result.confidence, float)
    assert 0.0 <= result.confidence <= 1.0
    assert isinstance(result.reasoning, str) and result.reasoning
    assert isinstance(result.actions_taken, list)


# ---------------------------------------------------------------------------
# CollectionsTool
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_collections_tool_returns_tool_output():
    from app.tools.collections import CollectionsTool

    tool = CollectionsTool()
    with patch("app.tools.collections._execute_collections", AsyncMock(return_value=_COLLECTIONS_RESULT)):
        result = await tool.execute(
            input_data={
                "execution_id": "exec_001",
                "tool_id": "tool_001",
                "invoice_id": "inv_001",
                "vendor": "Acme Corp",
                "amount_minor": 100000,
                "currency": "GBP",
                "due_date": date(2025, 1, 1),
                "days_overdue": 14,
                "previous_reminders_sent": 1,
                "customer_payment_history": {},
            },
            tenant_id="tenant_001",
        )

    assert isinstance(result, ToolOutput)
    assert isinstance(result.confidence, float)
    assert 0.0 <= result.confidence <= 1.0
    assert isinstance(result.reasoning, str) and result.reasoning
    assert isinstance(result.actions_taken, list)


# ---------------------------------------------------------------------------
# FraudDetectionTool
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fraud_detection_tool_returns_tool_output():
    from app.tools.fraud_detection import FraudDetectionTool

    tool = FraudDetectionTool()
    with patch("app.tools.fraud_detection._execute_fraud_detection", AsyncMock(return_value=_FRAUD_RESULT)):
        result = await tool.execute(
            input_data={
                "execution_id": "exec_001",
                "tool_id": "tool_001",
                "transaction_ids": ["txn_001"],
                "transaction_id": "txn_001",
                "amount_minor": 25000,
                "currency": "GBP",
                "counterparty": "Trusted Vendor",
                "transaction_type": "payment",
                "timestamp": datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
                "metadata": {},
            },
            tenant_id="tenant_001",
        )

    assert isinstance(result, ToolOutput)
    assert isinstance(result.confidence, float)
    assert 0.0 <= result.confidence <= 1.0
    assert isinstance(result.reasoning, str) and result.reasoning
    assert isinstance(result.actions_taken, list)
