"""
Fraud Score API — POST /v1/fraud/score.
# TODO: wire FraudDetectionTool in Phase 2
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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
    raise HTTPException(status_code=501, detail="Standalone fraud scoring is not yet available. Use the risk_compliance tool via POST /v1/execute instead.")
