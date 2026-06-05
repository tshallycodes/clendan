"""
Reconciliation Worker — sub-agent worker. Called by Financial Orchestrator as a tool.
Matches source and target datasets, flags discrepancies, and summarises drift.
# TODO: wire bank_aggregation_api and erp_sync_api in Phase 2
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from app.workers.base import BaseWorker, WorkerOutput, WorkerType


class ReconciliationInput(BaseModel):
    tenant_id: str
    source_dataset: list[dict]
    target_dataset: list[dict]
    period_start: date
    period_end: date


class ReconciliationOutput(BaseModel):
    matched: list[dict]
    unmatched: list[dict]
    flagged: list[dict]
    confidence: float
    summary: str
    reasoning: str


class ReconciliationWorker(BaseWorker):
    WORKER_TYPE = WorkerType.RECONCILIATION
    REQUIRED_TOOLS = ["bank_aggregation_api", "erp_sync_api"]
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> WorkerOutput:
        # TODO: wire bank_aggregation_api and erp_sync_api
        validated = ReconciliationInput(tenant_id=tenant_id, **input_data)
        result = ReconciliationOutput(
            matched=[],
            unmatched=[],
            flagged=[],
            confidence=0.0,
            summary="Stub",
            reasoning="Stub — wire bank_aggregation_api and erp_sync_api",
        )
        return WorkerOutput(
            worker_type=self.WORKER_TYPE,
            decision="reconciliation_complete",
            confidence=result.confidence,
            reasoning=result.reasoning,
            actions_taken=[],
            output_data=result.model_dump(),
        )
