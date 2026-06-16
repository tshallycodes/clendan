"""
Contract Parse API — POST /v1/parse/contract.
# TODO: wire contract extraction model in Phase 2
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.security import RequireOrgAuth

router = APIRouter(tags=["contract"])


class ParseContractRequest(BaseModel):
    file_bytes_b64: str
    content_type: str = "application/pdf"


@router.post("/parse/contract")
async def parse_contract(body: ParseContractRequest, current_user: RequireOrgAuth) -> dict:
    raise HTTPException(status_code=501, detail="Contract parsing is not yet available")
