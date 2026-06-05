"""
Revenue Recognition Worker — V2 worker stub. Not for production use until wired.
# TODO: wire contract_parser, erp_client in Phase 2
"""
from typing import Literal

from pydantic import BaseModel

from app.workers.base import BaseWorker, WorkerOutput, WorkerType


class RevenueRecognitionInput(BaseModel):
    tenant_id: str
    contract_id: str
    contract_document_ref: str
    billing_data: dict
    recognition_standard: Literal["ASC606", "IFRS15"]
    period: str


class RevenueRecognitionOutput(BaseModel):
    recognized_revenue_minor: int
    deferred_revenue_minor: int
    revenue_schedule: list[dict]
    journal_entries: list[dict]
    confidence: float
    reasoning: str


class RevenueRecognitionWorker(BaseWorker):
    WORKER_TYPE = WorkerType.REVENUE_RECOGNITION
    REQUIRED_TOOLS = ["contract_parser", "erp_client"]
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> WorkerOutput:
        validated = RevenueRecognitionInput(tenant_id=tenant_id, **input_data)
        result = RevenueRecognitionOutput(
            recognized_revenue_minor=0,
            deferred_revenue_minor=0,
            revenue_schedule=[],
            journal_entries=[],
            confidence=0.0,
            reasoning="Stub — not yet wired",
        )
        return WorkerOutput(
            worker_type=self.WORKER_TYPE,
            decision="revenue_scheduled",
            confidence=result.confidence,
            reasoning=result.reasoning,
            actions_taken=[],
            output_data=result.model_dump(),
        )
