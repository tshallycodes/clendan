"""
Expense Control Worker — sub-agent worker. Called by Financial Orchestrator as a tool.
Validates expense claims against policy rules and approves, rejects, or flags them.
# TODO: wire ocr_document_api and policy_rules_api in Phase 2
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.workers.base import BaseWorker, WorkerOutput, WorkerType


class ExpenseControlInput(BaseModel):
    tenant_id: str
    expense_claim_id: str
    amount_minor: int
    currency: str
    category: str
    receipt_document_ref: str
    submitted_by: str
    policy_rules: dict


class ExpenseControlOutput(BaseModel):
    decision: Literal["approved", "rejected", "flagged"]
    reason: str
    policy_violations: list[str]
    confidence: float
    reasoning: str


class ExpenseControlWorker(BaseWorker):
    WORKER_TYPE = WorkerType.EXPENSE_CONTROL
    REQUIRED_TOOLS = ["ocr_document_api", "policy_rules_api"]
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> WorkerOutput:
        # TODO: wire ocr_document_api and policy_rules_api
        validated = ExpenseControlInput(tenant_id=tenant_id, **input_data)
        result = ExpenseControlOutput(
            decision="flagged",
            reason="Stub",
            policy_violations=[],
            confidence=0.0,
            reasoning="Stub — wire ocr_document_api and policy_rules_api",
        )
        return WorkerOutput(
            worker_type=self.WORKER_TYPE,
            decision=result.decision,
            confidence=result.confidence,
            reasoning=result.reasoning,
            actions_taken=[],
            output_data=result.model_dump(),
        )
