"""
Fraud Score API stub — POST /v1/fraud/score.
# TODO: wire FraudDetectionWorker in Phase 2
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.responses import standard_response
from app.core.security import RequireAuth

router = APIRouter(tags=["fraud"])


class FraudScoreRequest(BaseModel):
    transaction_id: str
    amount_minor: int
    currency: str
    counterparty: str
    metadata: dict = {}


@router.post("/fraud/score")
async def score_fraud(body: FraudScoreRequest, payload: RequireAuth) -> dict:
    """Score a transaction for fraud risk. Stub — FraudDetectionWorker not yet wired."""
    return standard_response(
        data={
            "risk_score": 0.0,
            "risk_level": "low",
            "signals": [],
            "action": "allow",
            "confidence": 0.0,
            "note": "stub — not yet wired",
        }
    )
