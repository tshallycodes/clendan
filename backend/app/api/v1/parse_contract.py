"""
Contract Parse API — POST /v1/parse/contract.
Stub implementation — returns structured placeholder data until the extraction model is wired.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.responses import standard_response
from app.core.security import RequireOrgAuth

router = APIRouter(tags=["contract"])


class ParseContractRequest(BaseModel):
    file_bytes_b64: str
    content_type: str = "application/pdf"


@router.post("/parse/contract")
async def parse_contract(body: ParseContractRequest, current_user: RequireOrgAuth) -> dict:
    return standard_response(data={
        "counterparty": None,
        "contract_type": None,
        "effective_date": None,
        "expiry_date": None,
        "obligations": [],
        "amounts": [],
        "payment_terms": None,
        "governing_law": None,
        "confidence": 0.0,
        "status": "pending",
    })
