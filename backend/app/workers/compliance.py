"""
Compliance Worker — V3 worker stub. Not for production use.
V3 worker — not for production use. Regulatory review required.
# TODO: wire regulatory_rules_engine, reporting_client in Phase 3
"""
from pydantic import BaseModel

from app.workers.base import BaseWorker, WorkerOutput, WorkerType


class ComplianceInput(BaseModel):
    tenant_id: str
    transaction_id: str
    transaction_data: dict
    applicable_regulations: list[str]
    jurisdiction: str


class ComplianceOutput(BaseModel):
    compliant: bool
    violations: list[dict]
    required_actions: list[str]
    report_ref: str | None
    confidence: float
    reasoning: str


class ComplianceWorker(BaseWorker):
    WORKER_TYPE = WorkerType.COMPLIANCE
    REQUIRED_TOOLS = ["regulatory_rules_engine", "reporting_client"]
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> WorkerOutput:
        validated = ComplianceInput(tenant_id=tenant_id, **input_data)
        result = ComplianceOutput(
            compliant=True,
            violations=[],
            required_actions=[],
            report_ref=None,
            confidence=0.0,
            reasoning="Stub — not yet wired",
        )
        return WorkerOutput(
            worker_type=self.WORKER_TYPE,
            decision="compliant" if result.compliant else "non_compliant",
            confidence=result.confidence,
            reasoning=result.reasoning,
            actions_taken=[],
            output_data=result.model_dump(),
        )
