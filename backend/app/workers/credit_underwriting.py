"""
Credit Underwriting Worker — V3 worker stub. Not for production use.
V3 worker — not for production use. Requires regulatory review before deployment.
# TODO: wire credit_bureau_client, open_banking_client in Phase 3
"""
from typing import Literal

from pydantic import BaseModel

from app.workers.base import BaseWorker, WorkerOutput, WorkerType


class CreditUnderwritingInput(BaseModel):
    tenant_id: str
    application_id: str
    applicant_id: str
    requested_amount_minor: int
    currency: str
    credit_bureau_data: dict
    bank_transaction_history: list[dict]
    declared_income_minor: int


class CreditUnderwritingOutput(BaseModel):
    decision: Literal["approved", "rejected", "referred"]
    approved_amount_minor: int | None
    interest_rate_bps: int | None
    risk_grade: str
    risk_factors: list[str]
    confidence: float
    reasoning: str


class CreditUnderwritingWorker(BaseWorker):
    WORKER_TYPE = WorkerType.CREDIT_UNDERWRITING
    REQUIRED_TOOLS = ["credit_bureau_client", "open_banking_client"]
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> WorkerOutput:
        validated = CreditUnderwritingInput(tenant_id=tenant_id, **input_data)
        result = CreditUnderwritingOutput(
            decision="referred",
            approved_amount_minor=None,
            interest_rate_bps=None,
            risk_grade="unrated",
            risk_factors=[],
            confidence=0.0,
            reasoning="Stub — not yet wired",
        )
        return WorkerOutput(
            worker_type=self.WORKER_TYPE,
            decision=result.decision,
            confidence=result.confidence,
            reasoning=result.reasoning,
            actions_taken=[],
            output_data=result.model_dump(),
        )
