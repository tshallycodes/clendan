"""
Smoke tests for Phase 2/3 tool stubs.
Verifies each stub instantiates, executes against minimal valid input,
and returns a well-formed ToolOutput without making any external calls.
"""
from unittest.mock import AsyncMock, patch

import pytest

from app.tools.base import ToolOutput


_BASE_RESULT = {
    "decision": "auto_approved",
    "confidence": 0.85,
    "reasoning": "stub reasoning",
    "actions_taken": [],
    "output_data": {},
}

_REVENUE_RESULT = {
    "decision": "revenue_scheduled",
    "confidence": 0.85,
    "reasoning": "stub reasoning",
    "actions_taken": [],
    "recognition_method": "straight_line",
    "accounting_standard": "ASC606",
    "performance_obligations": [],
    "variable_consideration_minor": 0,
}

_CREDIT_RESULT = {
    "decision": "auto_approved",
    "confidence": 0.85,
    "reasoning": "stub reasoning",
    "actions_taken": [],
    "output_data": {
        "application_id": "a1", "decision": "auto_approved",
        "hard_rule_triggered": None, "credit_score": 750,
        "front_end_dti": "0.25", "back_end_dti": 0.35,
        "risk_grade": "A", "risk_factors": [], "mitigating_factors": [],
        "approved_amount_minor": 100000, "interest_rate_bps": 450,
        "conditions": [], "confidence": 0.85,
    },
}


class TestTreasuryToolStub:

    @pytest.mark.asyncio
    async def test_returns_tool_output(self):
        from app.tools.treasury import TreasuryTool

        tool = TreasuryTool()
        with patch("app.tools.treasury._execute_treasury", AsyncMock(return_value=_BASE_RESULT)):
            result = await tool.execute(
                input_data={
                    "execution_id": "exec_001",
                    "tool_id": "tool_001",
                    "accounts": [],
                    "forecast_horizon_days": 30,
                    "upcoming_payments": [],
                    "upcoming_receivables": [],
                },
                tenant_id="tenant_test",
            )

        assert isinstance(result, ToolOutput)
        assert 0.0 <= result.confidence <= 1.0
        assert isinstance(result.reasoning, str) and result.reasoning
        assert isinstance(result.actions_taken, list)


class TestRevenueRecognitionToolStub:

    @pytest.mark.asyncio
    async def test_returns_tool_output(self):
        from app.tools.revenue_recognition import RevenueRecognitionTool

        tool = RevenueRecognitionTool()
        with patch("app.tools.revenue_recognition._execute_revenue_recognition", AsyncMock(return_value=_REVENUE_RESULT)):
            result = await tool.execute(
                input_data={
                    "execution_id": "exec_001",
                    "tool_id": "tool_001",
                    "contract_id": "c1",
                    "contract_document_ref": "doc.pdf",
                    "billing_data": {},
                    "recognition_standard": "ASC606",
                    "period": "2026-05",
                },
                tenant_id="tenant_test",
            )

        assert isinstance(result, ToolOutput)
        assert 0.0 <= result.confidence <= 1.0
        assert isinstance(result.reasoning, str) and result.reasoning
        assert isinstance(result.actions_taken, list)


class TestCreditUnderwritingToolStub:

    @pytest.mark.asyncio
    async def test_returns_tool_output(self):
        from app.tools.credit_underwriting import CreditUnderwritingTool

        tool = CreditUnderwritingTool()
        with patch("app.tools.credit_underwriting._execute_credit_underwriting", AsyncMock(return_value=_CREDIT_RESULT)):
            result = await tool.execute(
                input_data={
                    "execution_id": "exec_001",
                    "tool_id": "tool_001",
                    "application_id": "a1",
                    "applicant_id": "u1",
                    "requested_amount_minor": 100000,
                    "currency": "GBP",
                    "credit_bureau_data": {},
                    "bank_transaction_history": [],
                    "declared_income_minor": 500000,
                    "application_data": {},
                },
                tenant_id="tenant_test",
            )

        assert isinstance(result, ToolOutput)
        assert 0.0 <= result.confidence <= 1.0
        assert isinstance(result.reasoning, str) and result.reasoning
        assert isinstance(result.actions_taken, list)


class TestComplianceToolStub:

    @pytest.mark.asyncio
    async def test_returns_tool_output(self):
        from app.tools.compliance import ComplianceTool

        tool = ComplianceTool()
        with patch("app.tools.compliance._execute_compliance", AsyncMock(return_value=_BASE_RESULT)):
            result = await tool.execute(
                input_data={
                    "execution_id": "exec_001",
                    "tool_id": "tool_001",
                    "transaction_id": "t1",
                    "transaction_ids": ["t1"],
                    "transaction_data": {},
                    "applicable_regulations": ["AML"],
                    "frameworks": ["AML"],
                    "jurisdiction": "UK",
                },
                tenant_id="tenant_test",
            )

        assert isinstance(result, ToolOutput)
        assert 0.0 <= result.confidence <= 1.0
        assert isinstance(result.reasoning, str) and result.reasoning
        assert isinstance(result.actions_taken, list)
