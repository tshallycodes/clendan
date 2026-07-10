"""
FreshBooks write client - create AP bills. FreshBooks has no journal-entry API, so it is a
bill-capable ERP target only (the erp_writer resolves journals to QuickBooks/Xero).
Called only through app/core/erp_writer.py, which gates every write behind erp_write_live.
"""
from app.core.logging import get_logger
from app.integrations.freshbooks import client as fb
from app.integrations.token_manager import get_valid_token

logger = get_logger(__name__)


async def _context(db, integration) -> tuple[str, str]:
    """Return (access_token, account_id) for a FreshBooks integration."""
    token = await get_valid_token(integration.id, db)
    me = await fb.get_me(token)
    account_id = fb.extract_account_id(me)
    return token, account_id


async def create_bill(db, tenant_id: str, integration, bill) -> dict:
    """Create an AP bill in FreshBooks from a Clendan bill row. Returns {external_id}."""
    token, account_id = await _context(db, integration)
    vendor_id = await fb.find_or_create_vendor(token, account_id, bill.contact_name or "Unknown vendor")
    issue_date = None
    if bill.issue_date:
        issue_date = bill.issue_date.date().isoformat() if hasattr(bill.issue_date, "date") else str(bill.issue_date)
    result = await fb.create_bill(
        token, account_id,
        vendor_id=vendor_id, bill_number=bill.number or bill.id,
        amount_minor=bill.total_cents, currency=bill.currency,
        issue_date=issue_date, description=bill.number or "Bill",
    )
    logger.info("freshbooks_bill_created", extra={"tenant_id": tenant_id, "bill_id": bill.id})
    return {"external_id": result["id"]}
