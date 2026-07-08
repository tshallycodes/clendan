"""SaaS billing routes - Stripe Checkout, Customer Portal, and subscription status.

Reads subscription state from the Tenant row (kept current by the billing webhook).
Write actions (checkout, portal) require owner/admin and go straight to Stripe;
subscription state is never trusted from the client - only the webhook mutates it.
"""
import uuid
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from prisma import Prisma
from pydantic import BaseModel, field_validator

from app.core.config import get_settings
from app.core.db import get_db_dep
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.core.security import CurrentUser, RequireOrgAuth, require_role
from app.integrations.stripe import billing as stripe_billing

logger = get_logger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])


class CheckoutRequest(BaseModel):
    plan: str

    @field_validator("plan")
    @classmethod
    def validate_plan(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if v not in stripe_billing.SELF_SERVE_PLANS:
            raise ValueError(
                f"plan must be one of: {', '.join(stripe_billing.SELF_SERVE_PLANS)}"
            )
        return v


@router.get("/subscription")
async def get_subscription(
    current_user: RequireOrgAuth,
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Returns the authenticated tenant's current plan and subscription state."""
    tenant = await db.tenant.find_unique(where={"id": current_user.tenant_id})
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    period_end: Optional[datetime] = tenant.current_period_end
    return standard_response(
        data={
            "plan": tenant.plan or "free",
            "status": tenant.subscription_status,
            "current_period_end": period_end.isoformat() if period_end else None,
            "cancel_at_period_end": tenant.cancel_at_period_end,
            "has_subscription": bool(tenant.stripe_subscription_id),
        }
    )


async def _ensure_customer(db: Prisma, current_user: CurrentUser) -> str:
    """Returns the tenant's Stripe customer id, creating and persisting one if needed."""
    tenant = await db.tenant.find_unique(where={"id": current_user.tenant_id})
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    if tenant.stripe_customer_id:
        return tenant.stripe_customer_id

    try:
        customer_id = await stripe_billing.create_customer(
            tenant_id=tenant.id,
            email=current_user.email,
            name=tenant.name,
        )
    except Exception as exc:
        logger.error("billing_create_customer_failed exc=%s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not create billing customer",
        )

    await db.tenant.update(
        where={"id": tenant.id}, data={"stripe_customer_id": customer_id}
    )
    return customer_id


@router.post("/checkout")
async def create_checkout(
    body: CheckoutRequest,
    current_user: Annotated[CurrentUser, require_role("owner", "admin")],
    db: Annotated[Prisma, Depends(get_db_dep)],
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Creates a Stripe Checkout Session for a self-serve plan. Returns the redirect URL."""
    price_id = stripe_billing.price_id_for_plan(body.plan)
    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Plan '{body.plan}' is not available for self-serve checkout",
        )

    customer_id = await _ensure_customer(db, current_user)
    frontend_url = get_settings().frontend_url.rstrip("/")

    try:
        url = await stripe_billing.create_checkout_session(
            customer_id=customer_id,
            price_id=price_id,
            tenant_id=current_user.tenant_id,
            success_url=f"{frontend_url}/settings?billing=success",
            cancel_url=f"{frontend_url}/settings?billing=canceled",
            idempotency_key=idempotency_key or f"checkout:{uuid.uuid4()}",
        )
    except Exception as exc:
        logger.error("billing_checkout_failed exc=%s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not start checkout",
        )

    return standard_response(data={"url": url})


@router.post("/portal")
async def create_portal(
    current_user: Annotated[CurrentUser, require_role("owner", "admin")],
    db: Annotated[Prisma, Depends(get_db_dep)],
):
    """Creates a Stripe Customer Portal session for managing an existing subscription."""
    tenant = await db.tenant.find_unique(where={"id": current_user.tenant_id})
    if not tenant or not tenant.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No billing customer yet - subscribe to a plan first",
        )

    frontend_url = get_settings().frontend_url.rstrip("/")
    try:
        url = await stripe_billing.create_portal_session(
            customer_id=tenant.stripe_customer_id,
            return_url=f"{frontend_url}/settings",
        )
    except Exception as exc:
        logger.error("billing_portal_failed exc=%s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not open billing portal",
        )

    return standard_response(data={"url": url})
