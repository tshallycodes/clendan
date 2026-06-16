"""
QuickBooks bill write — called by invoice_processing tool after AUTO_APPROVED decision.
Audit log is always written before this runs (enforced in invoice_processing.py).
"""
import json

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.quickbooks import client as qb

logger = get_logger(__name__)


async def write_bill_to_quickbooks(
    tenant_id: str,
    execution_id: str,
    vendor: str,
    invoice_number: str,
    amount_minor: int,
    currency: str,
    due_date: str | None,
    line_items: list[dict],
) -> dict:
    """
    Writes an approved invoice as a Bill in QuickBooks.

    Steps:
      1. Load QB integration credentials for tenant (zero trust — validates before use)
      2. Find or create vendor entity
      3. Resolve expense account ID
      4. Create bill (idempotent on DocNumber)

    Returns QB bill dict. Raises on any failure — caller decides whether to surface or swallow.
    """
    db = get_db()
    settings = get_settings()

    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "quickbooks", "status": "connected"}
    )
    if not integration:
        raise ValueError(f"No connected QuickBooks integration for tenant {tenant_id}")

    creds = json.loads(integration.encrypted_credentials)
    encrypted_access = creds["access_token"]
    realm_id = creds["realm_id"]
    sandbox = settings.quickbooks_sandbox

    vendor_id = await qb.find_or_create_vendor(
        encrypted_access=encrypted_access,
        realm_id=realm_id,
        vendor_name=vendor,
        sandbox=sandbox,
    )

    account_id = await qb.get_expense_account_id(
        encrypted_access=encrypted_access,
        realm_id=realm_id,
        sandbox=sandbox,
    )

    result = await qb.create_bill(
        encrypted_access=encrypted_access,
        realm_id=realm_id,
        vendor_id=vendor_id,
        account_id=account_id,
        invoice_number=invoice_number,
        amount_minor=amount_minor,
        currency=currency,
        due_date=due_date,
        line_items=line_items,
        sandbox=sandbox,
    )

    action = "created" if result.get("created") else "already_existed"
    logger.info(
        "qb_bill_%s",
        action,
        extra={
            "tenant_id": tenant_id,
            "execution_id": execution_id,
            "qb_bill_id": result["qb_bill_id"],
            "doc_number": result["doc_number"],
            "total_amount": result["total_amount"],
        },
    )

    return result
