"""
Smoke tests for Phase 2/3 tool stubs.
Verifies each stub instantiates, executes against minimal valid input,
and returns a well-formed ToolOutput without making any external calls.
"""
import pytest

from app.tools.base import ToolOutput


class TestTreasuryToolStub:

    @pytest.mark.asyncio
    async def test_returns_tool_output(self):
        from app.tools.treasury import TreasuryTool

        tool = TreasuryTool()
        result = await tool.execute(
            input_data={
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
        result = await tool.execute(
            input_data={
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
        result = await tool.execute(
            input_data={
                "application_id": "a1",
                "applicant_id": "u1",
                "requested_amount_minor": 100000,
                "currency": "GBP",
                "credit_bureau_data": {},
                "bank_transaction_history": [],
                "declared_income_minor": 500000,
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
        result = await tool.execute(
            input_data={
                "transaction_id": "t1",
                "transaction_data": {},
                "applicable_regulations": ["AML"],
                "jurisdiction": "UK",
            },
            tenant_id="tenant_test",
        )

        assert isinstance(result, ToolOutput)
        assert 0.0 <= result.confidence <= 1.0
        assert isinstance(result.reasoning, str) and result.reasoning
        assert isinstance(result.actions_taken, list)
