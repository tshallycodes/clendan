"""Stripe SaaS billing webhook - the single source of truth for subscription state.

Distinct from ``webhooks/stripe.py`` (Stripe Connect data ingestion): this endpoint
has its own signing secret and only mutates the tenant's own subscription fields.
Handlers are idempotent - re-applying the same event yields the same tenant state.
"""
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException, Request
from prisma import Prisma

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.core.responses import standard_response
from app.integrations.stripe import billing as stripe_billing
from app.integrations.stripe.client import verify_stripe_signature

_logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_HANDLED = {
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.payment_failed",
}


def _extract_price_id(subscription: dict) -> str:
    items = (subscription.get("items") or {}).get("data") or []
    if items:
        return (items[0].get("price") or {}).get("id", "") or ""
    return ""


def _period_end(subscription: dict) -> datetime | None:
    ts = subscription.get("current_period_end")
    return datetime.fromtimestamp(ts, tz=UTC) if ts else None


async def _resolve_tenant_id(db: Prisma, obj: dict) -> str | None:
    """Resolves the Clendan tenant from a Stripe object via metadata or customer id."""
    tenant_id = (obj.get("metadata") or {}).get("tenant_id") or obj.get("client_reference_id")
    if tenant_id:
        tenant = await db.tenant.find_unique(where={"id": tenant_id})
        if tenant:
            return tenant.id
    customer_id = obj.get("customer")
    if customer_id:
        tenant = await db.tenant.find_first(where={"stripe_customer_id": customer_id})
        if tenant:
            return tenant.id
    return None


async def _apply_subscription(db: Prisma, tenant_id: str, subscription: dict) -> None:
    """Writes plan/status/period from a subscription object. Idempotent."""
    price_id = _extract_price_id(subscription)
    await db.tenant.update(
        where={"id": tenant_id},
        data={
            "stripe_subscription_id": subscription.get("id"),
            "plan": stripe_billing.plan_for_price(price_id),
            "subscription_status": subscription.get("status"),
            "current_period_end": _period_end(subscription),
            "cancel_at_period_end": bool(subscription.get("cancel_at_period_end", False)),
        },
    )


@router.post("/stripe/billing")
async def stripe_billing_webhook(
    request: Request,
    stripe_signature: str = Header(..., alias="stripe-signature"),
):
    """Receives Stripe subscription lifecycle events for Clendan's own billing."""
    settings = get_settings()
    if not settings.stripe_billing_webhook_secret:
        _logger.error("stripe_billing_webhook_secret_not_configured")
        raise HTTPException(status_code=503, detail="Billing webhook not configured")

    body = await request.body()
    if not verify_stripe_signature(body, stripe_signature, settings.stripe_billing_webhook_secret):
        _logger.warning("stripe_billing_webhook_invalid_signature")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    event_type: str = payload.get("type", "")
    if event_type not in _HANDLED:
        return standard_response(data={"received": True})

    obj = (payload.get("data") or {}).get("object") or {}
    db = get_db()

    tenant_id = await _resolve_tenant_id(db, obj)
    if not tenant_id:
        _logger.warning("stripe_billing_webhook_no_tenant event=%s", event_type)
        return standard_response(data={"received": True})

    _logger.info("stripe_billing_webhook event=%s tenant_id=%s", event_type, tenant_id)

    if event_type == "checkout.session.completed":
        subscription_id = obj.get("subscription")
        if subscription_id:
            try:
                subscription = await stripe_billing.fetch_subscription(subscription_id)
                await _apply_subscription(db, tenant_id, subscription)
            except Exception as exc:
                _logger.error("stripe_billing_fetch_subscription_failed exc=%s", type(exc).__name__)
                raise HTTPException(status_code=502, detail="Failed to sync subscription")

    elif event_type in ("customer.subscription.created", "customer.subscription.updated"):
        await _apply_subscription(db, tenant_id, obj)

    elif event_type == "customer.subscription.deleted":
        await db.tenant.update(
            where={"id": tenant_id},
            data={
                "plan": "free",
                "subscription_status": "canceled",
                "stripe_subscription_id": None,
                "current_period_end": None,
                "cancel_at_period_end": False,
            },
        )

    elif event_type == "invoice.payment_failed":
        await db.tenant.update(
            where={"id": tenant_id},
            data={"subscription_status": "past_due"},
        )

    return standard_response(data={"received": True})
