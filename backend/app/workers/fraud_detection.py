"""
Fraud Detection Worker — sub-agent worker. Called by Financial Orchestrator as a tool.
Scores transactions for fraud risk and determines allow, flag, or block action.
# TODO: wire fraud_signals_api and transaction_history_api in Phase 2
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.workers.base import BaseWorker, WorkerOutput, WorkerType


class FraudDetectionInput(BaseModel):
    tenant_id: str
    transaction_id: str
    amount_minor: int
    currency: str
    counterparty: str
    transaction_type: str
    timestamp: datetime
    metadata: dict


class FraudDetectionOutput(BaseModel):
    risk_score: float
    risk_level: Literal["low", "medium", "high", "critical"]
    signals: list[str]
    action: Literal["allow", "flag", "block"]
    confidence: float
    reasoning: str


class FraudDetectionWorker(BaseWorker):
    WORKER_TYPE = WorkerType.FRAUD_DETECTION
    REQUIRED_TOOLS = ["fraud_signals_api", "transaction_history_api"]
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> WorkerOutput:
        # TODO: wire fraud_signals_api and transaction_history_api
        validated = FraudDetectionInput(tenant_id=tenant_id, **input_data)
        result = FraudDetectionOutput(
            risk_score=0.0,
            risk_level="low",
            signals=[],
            action="allow",
            confidence=0.0,
            reasoning="Stub — wire fraud_signals_api and transaction_history_api",
        )
        return WorkerOutput(
            worker_type=self.WORKER_TYPE,
            decision=result.action,
            confidence=result.confidence,
            reasoning=result.reasoning,
            actions_taken=[],
            output_data=result.model_dump(),
        )
