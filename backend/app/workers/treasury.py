"""
Treasury Worker — V2 worker stub. Not for production use until wired.
# TODO: wire plaid_client, bank_account_aggregator in Phase 2
"""
from typing import Literal

from pydantic import BaseModel

from app.workers.base import BaseWorker, WorkerOutput, WorkerType


class TreasuryInput(BaseModel):
    tenant_id: str
    accounts: list[dict]
    forecast_horizon_days: int
    upcoming_payments: list[dict]
    upcoming_receivables: list[dict]


class TreasuryOutput(BaseModel):
    current_balance_minor: int
    projected_balance_minor: int
    liquidity_risk: Literal["none", "low", "medium", "high"]
    recommendations: list[str]
    cash_forecast: list[dict]
    confidence: float
    reasoning: str


class TreasuryWorker(BaseWorker):
    WORKER_TYPE = WorkerType.TREASURY
    REQUIRED_TOOLS = ["plaid_client", "bank_account_aggregator"]
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> WorkerOutput:
        validated = TreasuryInput(tenant_id=tenant_id, **input_data)
        result = TreasuryOutput(
            current_balance_minor=0,
            projected_balance_minor=0,
            liquidity_risk="none",
            recommendations=[],
            cash_forecast=[],
            confidence=0.0,
            reasoning="Stub — not yet wired",
        )
        return WorkerOutput(
            worker_type=self.WORKER_TYPE,
            decision=result.liquidity_risk,
            confidence=result.confidence,
            reasoning=result.reasoning,
            actions_taken=[],
            output_data=result.model_dump(),
        )
