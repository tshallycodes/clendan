from datetime import datetime, UTC, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from prisma import Prisma
from pydantic import BaseModel

from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import RequireOrgAuth
from app.models.currency import SUPPORTED_CURRENCIES

logger = get_logger(__name__)
router = APIRouter(prefix="/currency", tags=["currency"])

_STALE_THRESHOLD_HOURS = 48


class PreferencePatch(BaseModel):
    currency: str


@router.get("/rates")
async def get_exchange_rates(
    _: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """
    Returns all current exchange rates (USD base) and staleness metadata.
    Rates older than 48 hours are flagged as stale — the cron job may have failed.
    """
    rates = await db.exchangerate.find_many(
        where={"base_currency": "USD"},
        order={"target_currency": "asc"},
    )

    rates_map = {r.target_currency: float(r.rate) for r in rates}

    newest_updated_at: datetime | None = None
    if rates:
        newest_updated_at = max(r.updated_at for r in rates)

    is_stale = False
    if newest_updated_at is None:
        is_stale = True
    else:
        age = datetime.now(UTC) - newest_updated_at.replace(tzinfo=UTC)
        is_stale = age > timedelta(hours=_STALE_THRESHOLD_HOURS)

    return standard_response(data={
        "rates": rates_map,
        "base_currency": "USD",
        "updated_at": newest_updated_at.isoformat() if newest_updated_at else None,
        "is_stale": is_stale,
        "supported_currencies": SUPPORTED_CURRENCIES,
    })


@router.get("/preferences")
async def get_currency_preference(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns the authenticated user's preferred display currency."""
    user = await db.user.find_first(
        where={"clerk_user_id": current_user.user_id, "tenant_id": current_user.tenant_id}
    )
    preferred = user.preferred_currency if user else "USD"
    return standard_response(data={"preferred_currency": preferred})


@router.patch("/preferences")
async def update_currency_preference(
    body: PreferencePatch,
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Updates the authenticated user's preferred display currency."""
    code = body.currency.upper()
    if code not in SUPPORTED_CURRENCIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported currency: {code}. Must be one of the 50 supported currencies.",
        )

    user = await db.user.find_first(
        where={"clerk_user_id": current_user.user_id, "tenant_id": current_user.tenant_id}
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User record not found")

    await db.user.update(
        where={"id": user.id},
        data={"preferred_currency": code},
    )

    logger.info(
        "currency_preference_updated",
        extra={"user_id": current_user.user_id, "currency": code},
    )
    return standard_response(data={"preferred_currency": code})
