"""
FreshBooks expense write — creates an expense for a document pushed from Document Intelligence.
Uses the standard Expenses API (universally available) rather than the Bills API (feature-gated).
"""
import asyncio
import random
from datetime import UTC, datetime

import httpx

from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.encryption import decrypt_credentials, encrypt_credentials
from app.integrations.freshbooks import client as fb

logger = get_logger(__name__)

FRESHBOOKS_API_BASE = "https://api.freshbooks.com"
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0


async def _retry(fn, *args, **kwargs):
    last_exc: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            return await fn(*args, **kwargs)
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.NetworkError) as exc:
            last_exc = exc
            if attempt < MAX_ATTEMPTS - 1:
                wait = BACKOFF_SECONDS * (2 ** attempt) + random.uniform(0, 0.5)
                logger.warning(
                    "freshbooks_write_retry attempt=%d/%d retry_in=%.1fs",
                    attempt + 1, MAX_ATTEMPTS, wait,
                )
                await asyncio.sleep(wait)
    assert last_exc is not None
    raise last_exc


async def create_bill(
    tenant_id: str,
    vendor: str,
    invoice_number: str,
    amount_minor: int,
    currency: str,
    expense_date: str | None = None,
) -> dict:
    """
    Creates an expense in FreshBooks for the given tenant.
    Uses Expenses API (not Bills) — available on all FreshBooks plans.
    Decrypts credentials from DB. Returns {"freshbooks_expense_id": str}.
    Raises ValueError if no connected integration or credentials incomplete.
    """
    db = get_db()
    logger.info("freshbooks_create_expense_start", extra={
        "tenant_id": tenant_id, "vendor": vendor,
        "invoice_number": invoice_number, "amount_minor": amount_minor,
        "currency": currency,
    })

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "freshbooks", "status": "connected"}
    )
    if not integration:
        logger.error("freshbooks_no_connected_integration", extra={"tenant_id": tenant_id})
        raise ValueError(f"No connected FreshBooks integration for tenant {tenant_id}")

    creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    access_token: str = creds.get("access_token", "")
    account_id: str = creds.get("account_id", "")

    token_expiry_at = creds.get("token_expiry_at")
    if token_expiry_at:
        try:
            if datetime.fromisoformat(token_expiry_at) <= datetime.now(UTC):
                logger.info("freshbooks_write_token_expired_refreshing", extra={"tenant_id": tenant_id})
                new_tokens = await fb.refresh_token(creds["refresh_token"])
                creds = {**creds, **new_tokens}
                access_token = creds["access_token"]
                await db.integration.update(
                    where={"id": integration.id},
                    data={"encrypted_credentials": encrypt_credentials(creds, tenant_id)},
                )
        except Exception as exc:
            logger.error("freshbooks_write_token_refresh_failed", extra={"tenant_id": tenant_id, "error": type(exc).__name__})

    if not access_token or not account_id:
        logger.error("freshbooks_credentials_incomplete", extra={
            "tenant_id": tenant_id,
            "has_access_token": bool(access_token),
            "has_account_id": bool(account_id),
        })
        raise ValueError("FreshBooks credentials missing access_token or account_id")

    # Resolve category_id — required by FreshBooks Expenses API. Cache in creds.
    category_id: int | None = creds.get("default_category_id")
    if category_id is None:
        try:
            categories = await fb.get_expense_categories(access_token, account_id)
            if categories:
                other = next((c for c in categories if "other" in c.get("name", "").lower()), None)
                category_id = int((other or categories[0])["id"])
                creds["default_category_id"] = category_id
                await db.integration.update(
                    where={"id": integration.id},
                    data={"encrypted_credentials": encrypt_credentials(creds, tenant_id)},
                )
        except Exception as exc:
            logger.warning("freshbooks_category_lookup_failed", extra={"tenant_id": tenant_id, "error": type(exc).__name__})

    # staffid is account-scoped — try membership_id, then business_id, then user_id.
    # The global user_id (freshbooks_user_id) is rejected by FreshBooks as invalid.
    staff_id: int | None = (
        creds.get("freshbooks_membership_id")
        or creds.get("freshbooks_business_id")
        or creds.get("freshbooks_user_id")
    )
    logger.info("freshbooks_staff_id_resolved", extra={"tenant_id": tenant_id, "staff_id": staff_id})

    amount_str = str(round(amount_minor / 100.0, 2))
    from datetime import date as _date
    expense_payload: dict = {
        "amount": {"amount": amount_str, "code": currency.upper()},
        "vendor": vendor,
        "notes": f"Invoice {invoice_number} from {vendor}",
        "date": expense_date or _date.today().isoformat(),
    }
    if category_id is not None:
        expense_payload["category_id"] = category_id
    if staff_id is not None:
        expense_payload["staffid"] = staff_id

    async def _call():
        url = f"{FRESHBOOKS_API_BASE}/accounting/account/{account_id}/expenses/expenses"
        logger.info("freshbooks_http_request", extra={
            "tenant_id": tenant_id, "invoice_number": invoice_number, "url": url,
        })
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json={"expense": expense_payload},
                timeout=15.0,
            )
            logger.info("freshbooks_http_response", extra={
                "tenant_id": tenant_id, "invoice_number": invoice_number,
                "status_code": resp.status_code,
            })
            if not resp.is_success:
                logger.error("freshbooks_http_error", extra={
                    "tenant_id": tenant_id, "invoice_number": invoice_number,
                    "status_code": resp.status_code, "response_body": resp.text,
                })
            resp.raise_for_status()
            return resp.json()

    raw = await _retry(_call)
    expense_id = str(
        raw.get("response", {}).get("result", {}).get("expense", {}).get("id", "")
    )
    logger.info(
        "freshbooks_expense_created",
        extra={
            "tenant_id": tenant_id,
            "freshbooks_expense_id": expense_id,
            "invoice_number": invoice_number,
        },
    )
    return {"freshbooks_expense_id": expense_id}
