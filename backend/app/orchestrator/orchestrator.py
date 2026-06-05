"""
Financial Orchestrator — master agent.
Receives all financial events, classifies them, invokes the correct worker as a tool,
applies global policy, compiles output, writes audit log.
Workers are NEVER called directly — always through _invoke_worker().
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.core.logging import get_logger
from app.orchestrator.registry import get_worker
from app.workers.base import WorkerOutput, WorkerType

logger = get_logger(__name__)

EVENT_TO_WORKER: dict[str, WorkerType] = {
    "invoice_received": WorkerType.INVOICE_PROCESSING,
    "transaction_posted": WorkerType.ACCOUNTANT,
    "expense_submitted": WorkerType.EXPENSE_CONTROL,
    "reconciliation_requested": WorkerType.RECONCILIATION,
    "fraud_check_requested": WorkerType.FRAUD_DETECTION,
    "collection_triggered": WorkerType.COLLECTIONS,
    "revenue_recognition_run": WorkerType.REVENUE_RECOGNITION,
    "compliance_check_requested": WorkerType.COMPLIANCE,
}

EventType = Literal[
    "invoice_received",
    "transaction_posted",
    "expense_submitted",
    "reconciliation_requested",
    "fraud_check_requested",
    "collection_triggered",
    "revenue_recognition_run",
    "compliance_check_requested",
]


class FinancialEvent(BaseModel):
    event_id: str
    tenant_id: str
    event_type: EventType
    payload: dict
    timestamp: datetime
    idempotency_key: str


class OrchestratorOutput(BaseModel):
    event_id: str
    worker_type: WorkerType
    decision: str
    confidence: float
    reasoning: str
    actions_taken: list[str]
    trace_id: str
    timestamp: datetime


class FinancialOrchestrator:

    async def handle_event(self, event: FinancialEvent, tenant_id: str) -> OrchestratorOutput:
        """Entry point. Classify → select worker → invoke → policy → output."""
        worker_type = await self._classify_event(event)
        worker_output = await self._invoke_worker(worker_type, event.payload, tenant_id)
        return await self._compile_output(event, worker_output)

    async def _classify_event(self, event: FinancialEvent) -> WorkerType:
        """Determine which worker should handle this event."""
        worker_type = EVENT_TO_WORKER.get(event.event_type)
        if worker_type is None:
            raise ValueError(f"No worker registered for event type: {event.event_type}")
        return worker_type

    async def _invoke_worker(
        self,
        worker_type: WorkerType,
        input_data: dict,
        tenant_id: str,
    ) -> WorkerOutput:
        """
        Call a sub-agent worker as a tool.
        All worker invocations go through here — never directly.
        # TODO: add retries, circuit breaker, timeout handling
        """
        worker = get_worker(worker_type)
        logger.info(
            "invoking_worker",
            extra={"worker_type": worker_type, "tenant_id": tenant_id},
        )
        return await worker.execute(input_data, tenant_id)

    async def _compile_output(
        self,
        event: FinancialEvent,
        worker_output: WorkerOutput,
    ) -> OrchestratorOutput:
        """Compile final decision and reasoning trace for audit."""
        return OrchestratorOutput(
            event_id=event.event_id,
            worker_type=worker_output.worker_type,
            decision=worker_output.decision,
            confidence=worker_output.confidence,
            reasoning=worker_output.reasoning,
            actions_taken=worker_output.actions_taken,
            trace_id=event.idempotency_key,
            timestamp=event.timestamp,
        )
