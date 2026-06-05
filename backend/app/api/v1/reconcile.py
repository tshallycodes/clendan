"""
Reconciliation API stub — POST /v1/reconcile.
# TODO: wire ReconciliationWorker in Phase 2
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.responses import standard_response
from app.core.security import RequireAuth

router = APIRouter(tags=["reconciliation"])


class ReconcileRequest(BaseModel):
    source_dataset: list[dict]
    target_dataset: list[dict]


@router.post("/reconcile")
async def reconcile_documents(body: ReconcileRequest, payload: RequireAuth) -> dict:
    """Reconcile two datasets. Stub — ReconciliationWorker not yet wired."""
    return standard_response(
        data={
            "matched": [],
            "unmatched": [],
            "flagged": [],
            "confidence": 0.0,
            "note": "stub — not yet wired",
        }
    )
