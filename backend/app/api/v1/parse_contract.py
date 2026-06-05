"""
Contract Parse API stub — POST /v1/parse/contract.
# TODO: wire contract extraction model in Phase 2
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.responses import standard_response
from app.core.security import RequireAuth

router = APIRouter(tags=["contract"])


class ParseContractRequest(BaseModel):
    file_bytes_b64: str
    content_type: str = "application/pdf"


@router.post("/parse/contract")
async def parse_contract(body: ParseContractRequest, payload: RequireAuth) -> dict:
    """Parse a contract document. Stub — contract extraction model not yet wired."""
    return standard_response(
        data={
            "counterparty": "",
            "payment_terms": "",
            "renewal_date": None,
            "obligations": [],
            "amounts": [],
            "governing_law": "",
            "confidence": 0.0,
            "note": "stub — not yet wired",
        }
    )
