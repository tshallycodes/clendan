"""
Plaid webhook receiver with JWT signature verification.
Plaid signs each webhook with a rotating key pair fetched from their JWKS endpoint.
Verification: decode JWT header → fetch matching key → verify signature → check iat freshness.
"""
import time
from typing import Any

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from jose import JWTError, jwt
from jose.exceptions import JWKError

from app.core.logging import get_logger
from app.core.responses import standard_response
from app.integrations.plaid.sync import enqueue_plaid_sync

_logger = get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

PLAID_JWKS_URL = "https://api.plaid.com/webhook_verification_key/get"
MAX_TOKEN_AGE_SECONDS = 300  # 5 minutes

_jwks_cache: dict[str, Any] = {}


async def _fetch_plaid_key(key_id: str) -> dict:
    """Fetch Plaid's verification key for the given key ID."""
    if key_id in _jwks_cache:
        return _jwks_cache[key_id]

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(PLAID_JWKS_URL, json={"key_id": key_id})
        resp.raise_for_status()
        data = resp.json()

    key = data.get("key")
    if not key:
        raise ValueError(f"No key returned for key_id={key_id}")

    _jwks_cache[key_id] = key
    return key


async def _verify_plaid_token(token: str) -> dict:
    """
    Verify a Plaid-Verification-Token JWT.
    Returns decoded payload if valid; raises HTTPException if not.
    """
    try:
        header = jwt.get_unverified_header(token)
        key_id = header.get("kid")
        if not key_id:
            raise HTTPException(status_code=401, detail="Webhook token missing key ID")

        key = await _fetch_plaid_key(key_id)

        payload: dict = jwt.decode(
            token,
            key,
            algorithms=["ES256"],
            options={"verify_aud": False},
        )

        issued_at = payload.get("iat", 0)
        if time.time() - issued_at > MAX_TOKEN_AGE_SECONDS:
            raise HTTPException(status_code=401, detail="Webhook token has expired")

        return payload

    except (JWTError, JWKError) as exc:
        _logger.warning("plaid_webhook_invalid_token", extra={"error": str(exc)})
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    except httpx.HTTPError as exc:
        _logger.error("plaid_jwks_fetch_failed", extra={"error": str(exc)})
        raise HTTPException(status_code=502, detail="Could not verify webhook signature")


@router.post("/plaid")
async def plaid_webhook(
    request: Request,
    plaid_verification_token: str = Header(..., alias="Plaid-Verification-Token"),
):
    """
    Receives and verifies Plaid webhooks.
    Signature must be verified before any processing — unverified webhooks are rejected.
    """
    await _verify_plaid_token(plaid_verification_token)

    body = await request.json()
    webhook_type = body.get("webhook_type", "")
    webhook_code = body.get("webhook_code", "")
    item_id = body.get("item_id", "")

    _logger.info(
        "plaid_webhook_received",
        extra={"webhook_type": webhook_type, "webhook_code": webhook_code},
    )

    if webhook_type == "TRANSACTIONS" and webhook_code in (
        "SYNC_UPDATES_AVAILABLE",
        "DEFAULT_UPDATE",
        "INITIAL_UPDATE",
    ):
        # Find the integration for this Plaid item and enqueue a sync
        from app.core.db import get_db
        db = get_db()
        integration = await db.integration.find_first(
            where={"type": "plaid", "status": "connected"}
        )
        if integration:
            try:
                await enqueue_plaid_sync(
                    integration_id=integration.id,
                    tenant_id=integration.tenant_id,
                )
            except Exception as exc:
                _logger.error("plaid_webhook_enqueue_failed", extra={"error": str(exc)})

    elif webhook_type == "ITEM" and webhook_code == "ERROR":
        _logger.warning("plaid_item_error", extra={"item_id": item_id, "error": body.get("error", {})})

    return standard_response(data={"received": True})
