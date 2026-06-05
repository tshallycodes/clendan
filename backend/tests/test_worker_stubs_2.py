"""
Smoke tests for Phase 2/3 worker stubs.
Verifies each stub instantiates, executes against minimal valid input,
and returns a well-formed WorkerOutput without making any external calls.
"""
import pytest

from app.workers.base import WorkerOutput


class TestTreasuryWorkerStub:

    @pytest.mark.asyncio
    async def test_returns_worker_output(self):
        from app.workers.treasury import TreasuryWorker

        worker = TreasuryWorker()
        result = await worker.execute(
            input_data={
                "accounts": [],
                "forecast_horizon_days": 30,
                "upcoming_payments": [],
                "upcoming_receivables": [],
            },
            tenant_id="tenant_test",
        )

        assert isinstance(result, WorkerOutput)
        assert 0.0 <= result.confidence <= 1.0
        assert isinstance(result.reasoning, str) and result.reasoning
        assert isinstance(result.actions_taken, list)


class TestRevenueRecognitionWorkerStub:

    @pytest.mark.asyncio
    async def test_returns_worker_output(self):
        from app.workers.revenue_recognition import RevenueRecognitionWorker

        worker = RevenueRecognitionWorker()
        result = await worker.execute(
            input_data={
                "contract_id": "c1",
                "contract_document_ref": "doc.pdf",
                "billing_data": {},
                "recognition_standard": "ASC606",
                "period": "2026-05",
            },
            tenant_id="tenant_test",
        )

        assert isinstance(result, WorkerOutput)
        assert 0.0 <= result.confidence <= 1.0
        assert isinstance(result.reasoning, str) and result.reasoning
        assert isinstance(result.actions_taken, list)


class TestCreditUnderwritingWorkerStub:

    @pytest.mark.asyncio
    async def test_returns_worker_output(self):
        from app.workers.credit_underwriting import CreditUnderwritingWorker

        worker = CreditUnderwritingWorker()
        result = await worker.execute(
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

        assert isinstance(result, WorkerOutput)
        assert 0.0 <= result.confidence <= 1.0
        assert isinstance(result.reasoning, str) and result.reasoning
        assert isinstance(result.actions_taken, list)


class TestComplianceWorkerStub:

    @pytest.mark.asyncio
    async def test_returns_worker_output(self):
        from app.workers.compliance import ComplianceWorker

        worker = ComplianceWorker()
        result = await worker.execute(
            input_data={
                "transaction_id": "t1",
                "transaction_data": {},
                "applicable_regulations": ["AML"],
                "jurisdiction": "UK",
            },
            tenant_id="tenant_test",
        )

        assert isinstance(result, WorkerOutput)
        assert 0.0 <= result.confidence <= 1.0
        assert isinstance(result.reasoning, str) and result.reasoning
        assert isinstance(result.actions_taken, list)
