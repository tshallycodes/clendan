"""
Financial Orchestrator unit tests.
No external API connections — workers execute in-process via stubs.
"""
import pytest
from datetime import datetime, UTC

from app.orchestrator.orchestrator import FinancialEvent, FinancialOrchestrator, OrchestratorOutput
from app.workers.base import WorkerType


def _make_event(event_type: str = "invoice_received") -> FinancialEvent:
    return FinancialEvent(
        event_id="evt_test_001",
        tenant_id="tenant_test",
        event_type=event_type,
        payload={},
        timestamp=datetime.now(UTC),
        idempotency_key="idempotency_test_001",
    )


class TestFinancialOrchestrator:

    @pytest.mark.asyncio
    async def test_handle_event_returns_orchestrator_output(self):
        orchestrator = FinancialOrchestrator()
        event = _make_event("invoice_received")
        result = await orchestrator.handle_event(event, tenant_id="tenant_test")
        assert isinstance(result, OrchestratorOutput)

    @pytest.mark.asyncio
    async def test_invoice_received_routes_to_invoice_processing_worker(self):
        orchestrator = FinancialOrchestrator()
        event = _make_event("invoice_received")
        result = await orchestrator.handle_event(event, tenant_id="tenant_test")
        assert result.worker_type == WorkerType.INVOICE_PROCESSING

    @pytest.mark.asyncio
    async def test_decision_is_non_empty_string(self):
        orchestrator = FinancialOrchestrator()
        event = _make_event("invoice_received")
        result = await orchestrator.handle_event(event, tenant_id="tenant_test")
        assert isinstance(result.decision, str)
        assert len(result.decision) > 0

    @pytest.mark.asyncio
    async def test_trace_id_matches_idempotency_key(self):
        orchestrator = FinancialOrchestrator()
        event = _make_event("invoice_received")
        result = await orchestrator.handle_event(event, tenant_id="tenant_test")
        assert result.trace_id == event.idempotency_key

    @pytest.mark.asyncio
    async def test_event_id_preserved_in_output(self):
        orchestrator = FinancialOrchestrator()
        event = _make_event("invoice_received")
        result = await orchestrator.handle_event(event, tenant_id="tenant_test")
        assert result.event_id == event.event_id

    @pytest.mark.asyncio
    async def test_transaction_posted_routes_to_accountant(self):
        orchestrator = FinancialOrchestrator()
        event = _make_event("transaction_posted")
        result = await orchestrator.handle_event(event, tenant_id="tenant_test")
        assert result.worker_type == WorkerType.ACCOUNTANT

    @pytest.mark.asyncio
    async def test_fraud_check_routes_to_fraud_detection(self):
        """Test classification only — invoke worker directly via classify to avoid validation."""
        orchestrator = FinancialOrchestrator()
        event = _make_event("fraud_check_requested")
        worker_type = await orchestrator._classify_event(event)
        assert worker_type == WorkerType.FRAUD_DETECTION

    @pytest.mark.asyncio
    async def test_reconciliation_requested_routes_correctly(self):
        """Test classification only — invoke worker directly via classify to avoid validation."""
        orchestrator = FinancialOrchestrator()
        event = _make_event("reconciliation_requested")
        worker_type = await orchestrator._classify_event(event)
        assert worker_type == WorkerType.RECONCILIATION

    @pytest.mark.asyncio
    async def test_classify_event_raises_for_unknown_type(self):
        import types
        orchestrator = FinancialOrchestrator()
        fake_event = types.SimpleNamespace(event_type="unknown_event_type")
        with pytest.raises(ValueError, match="No worker registered for event type"):
            await orchestrator._classify_event(fake_event)
