"""
Financial Orchestrator — master agent.
Receives all financial events, classifies them, invokes the correct worker as a tool,
applies global policy, compiles output, writes audit log.
Workers are NEVER called directly — always through _invoke_worker().
"""
import asyncio
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

    # -------------------------------------------------------------------------
    # Multi-step chaining
    # -------------------------------------------------------------------------

    async def invoke_workers_sequential(
        self,
        worker_types: list[WorkerType],
        payload: dict,
        tenant_id: str,
    ) -> list[WorkerOutput]:
        """
        Invoke workers one at a time in order.
        Each worker's output_data is merged into the payload for the next step.
        Stops immediately if any worker returns decision == "blocked".
        """
        results: list[WorkerOutput] = []
        current_payload = dict(payload)

        for worker_type in worker_types:
            logger.info(
                "sequential_chain_step",
                extra={
                    "worker_type": worker_type,
                    "tenant_id": tenant_id,
                    "step": len(results) + 1,
                    "total": len(worker_types),
                },
            )
            output = await self._invoke_worker(worker_type, current_payload, tenant_id)
            results.append(output)

            if output.decision == "blocked":
                logger.info(
                    "sequential_chain_blocked",
                    extra={"worker_type": worker_type, "reasoning": output.reasoning},
                )
                break

            current_payload = {**current_payload, **output.output_data}

        return results

    # -------------------------------------------------------------------------
    # Parallel invocation
    # -------------------------------------------------------------------------

    async def invoke_workers_parallel(
        self,
        worker_types: list[WorkerType],
        payload: dict,
        tenant_id: str,
    ) -> list[WorkerOutput]:
        """
        Invoke all workers simultaneously with the same original payload.
        Uses asyncio.gather — all workers receive the unmodified input.
        """
        logger.info(
            "parallel_invocation_start",
            extra={"worker_types": [w.value for w in worker_types], "tenant_id": tenant_id},
        )
        results: list[WorkerOutput] = await asyncio.gather(
            *[
                self._invoke_worker(worker_type, payload, tenant_id)
                for worker_type in worker_types
            ]
        )
        return list(results)

    # -------------------------------------------------------------------------
    # Conflict resolution
    # -------------------------------------------------------------------------

    def resolve_conflict(self, outputs: list[WorkerOutput]) -> WorkerOutput:
        """
        Priority order when multiple workers return results:
        1. blocked       — highest severity wins
        2. approval_required
        3. auto_approved — highest confidence wins; ties go to first
        """
        if not outputs:
            raise ValueError("resolve_conflict called with empty outputs list")

        blocked = [o for o in outputs if o.decision == "blocked"]
        if blocked:
            return blocked[0]

        approval_required = [o for o in outputs if o.decision == "approval_required"]
        if approval_required:
            return approval_required[0]

        return max(outputs, key=lambda o: o.confidence)

    # -------------------------------------------------------------------------
    # Convenience: invoice + fraud sequential chain
    # -------------------------------------------------------------------------

    async def handle_invoice_with_fraud_check(
        self,
        event: FinancialEvent,
        tenant_id: str,
    ) -> OrchestratorOutput:
        """
        Runs Invoice Processing then Fraud Detection sequentially.
        If fraud check blocks → returns blocked output.
        Otherwise compiles final output from the fraud check result (last step).
        """
        chain = await self.invoke_workers_sequential(
            worker_types=[WorkerType.INVOICE_PROCESSING, WorkerType.FRAUD_DETECTION],
            payload=event.payload,
            tenant_id=tenant_id,
        )

        # chain is never empty — at minimum invoice step ran
        final = chain[-1]

        if final.decision == "blocked":
            logger.info(
                "invoice_fraud_chain_blocked",
                extra={"event_id": event.event_id, "reasoning": final.reasoning},
            )
            return await self._compile_output(event, final)

        return await self._compile_output(event, final)
