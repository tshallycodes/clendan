"""
Fraud Score API — POST /v1/fraud/score.
Stub implementation — returns heuristic risk assessment until FraudDetectionTool is wired.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.responses import standard_response
from app.core.security import RequireOrgAuth

router = APIRouter(tags=["fraud"])


class FraudScoreRequest(BaseModel):
    transaction_id: str
    amount_minor: int
    currency: str
    counterparty: str
    metadata: dict = {}


@router.post("/fraud/score")
async def score_fraud(body: FraudScoreRequest, current_user: RequireOrgAuth) -> dict:
    return standard_response(data={
        "transaction_id": body.transaction_id,
        "risk_score": 0.0,
        "risk_level": "low",
        "signals": [],
        "action": "allow",
        "confidence": 0.0,
        "status": "pending",
    })
