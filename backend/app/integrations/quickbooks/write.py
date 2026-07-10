"""
QuickBooks bill write — called by invoice_processing tool after AUTO_APPROVED decision.
Audit log is always written before this runs (enforced in invoice_processing.py).
"""
from datetime import UTC, datetime

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.integrations.encryption import decrypt_credentials, encrypt_credentials
from app.integrations.quickbooks import client as qb

logger = get_logger(__name__)


async def _load_qb_credentials(db, tenant_id: str) -> tuple[str, str, bool]:
    """Load and (if expired) refresh QuickBooks credentials for the tenant.

    Returns (access_token, realm_id, sandbox). Raises if there is no connected QuickBooks
    integration or the stored credentials are incomplete. Shared by every QB writer.
    """
    settings = get_settings()
    integration = await db.integration.find_first(
        where={"tenant_id": tenant_id, "type": "quickbooks", "status": "connected"}
    )
    if not integration:
        logger.error("qb_no_connected_integration", extra={"tenant_id": tenant_id})
        raise ValueError(f"No connected QuickBooks integration for tenant {tenant_id}")

    creds = decrypt_credentials(integration.encrypted_credentials, tenant_id)
    access_token = creds.get("access_token", "")
    realm_id = creds.get("realm_id", "")

    token_expiry_at = creds.get("token_expiry_at")
    if token_expiry_at:
        try:
            if datetime.fromisoformat(token_expiry_at) <= datetime.now(UTC):
                logger.info("qb_write_token_expired_refreshing", extra={"tenant_id": tenant_id})
                new_tokens = await qb.refresh_token(creds["refresh_token"])
                creds = {**creds, **new_tokens}
                access_token = creds["access_token"]
                await db.integration.update(
                    where={"id": integration.id},
                    data={"encrypted_credentials": encrypt_credentials(creds, tenant_id)},
                )
        except Exception as exc:
            logger.error("qb_write_token_refresh_failed", extra={"tenant_id": tenant_id, "error": type(exc).__name__})

    if not access_token or not realm_id:
        logger.error("qb_credentials_incomplete", extra={
            "tenant_id": tenant_id, "has_access_token": bool(access_token), "has_realm_id": bool(realm_id),
        })
        raise ValueError("QuickBooks credentials missing access_token or realm_id")

    return access_token, realm_id, settings.quickbooks_sandbox


async def write_journal_to_quickbooks(
    tenant_id: str,
    *,
    description: str,
    lines: list[dict],
) -> dict:
    """Post a Clendan journal entry to QuickBooks as a JournalEntry.

    ``lines`` are provider-neutral: {account_code, account_name, posting_type, amount_minor,
    description}. Each line's account is resolved to a QB AccountRef by account number, then
    by name; an unmappable account raises rather than posting a wrong entry.
    """
    db = get_db()
    access_token, realm_id, sandbox = await _load_qb_credentials(db, tenant_id)

    accounts = await qb.get_accounts(access_token, realm_id, sandbox)
    by_num: dict[str, str] = {}
    by_name: dict[str, str] = {}
    for a in accounts:
        num = str(a.get("AcctNum") or "").strip()
        name = str(a.get("Name") or "").strip().lower()
        if num:
            by_num[num] = a["Id"]
        if name:
            by_name[name] = a["Id"]

    qb_lines: list[dict] = []
    for ln in lines:
        code = str(ln.get("account_code") or "").strip()
        name = str(ln.get("account_name") or "").strip().lower()
        account_id = by_num.get(code) or by_name.get(name)
        if not account_id:
            raise ValueError(
                f"Cannot map journal line account '{ln.get('account_code')}/{ln.get('account_name')}' "
                "to a QuickBooks account"
            )
        qb_lines.append({
            "account_id": account_id,
            "posting_type": ln["posting_type"],
            "amount_minor": ln["amount_minor"],
            "description": ln.get("description", ""),
        })

    result = await qb.create_journal_entry(
        access_token, realm_id, description=description, lines=qb_lines, sandbox=sandbox,
    )
    logger.info("qb_journal_created", extra={
        "tenant_id": tenant_id, "qb_journal_id": result["qb_journal_id"], "line_count": len(qb_lines),
    })
    return result


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

    logger.info("qb_write_bill_start", extra={
        "tenant_id": tenant_id, "execution_id": execution_id,
        "vendor": vendor, "invoice_number": invoice_number,
        "amount_minor": amount_minor, "currency": currency, "due_date": due_date,
    })

    encrypted_access, realm_id, sandbox = await _load_qb_credentials(db, tenant_id)

    logger.info("qb_finding_vendor", extra={"tenant_id": tenant_id, "vendor": vendor})
    vendor_id = await qb.find_or_create_vendor(
        encrypted_access=encrypted_access,
        realm_id=realm_id,
        vendor_name=vendor,
        sandbox=sandbox,
    )
    logger.info("qb_vendor_resolved", extra={"tenant_id": tenant_id, "vendor_id": vendor_id})

    logger.info("qb_resolving_expense_account", extra={"tenant_id": tenant_id})
    account_id = await qb.get_expense_account_id(
        encrypted_access=encrypted_access,
        realm_id=realm_id,
        sandbox=sandbox,
    )
    logger.info("qb_expense_account_resolved", extra={"tenant_id": tenant_id, "account_id": account_id})

    logger.info("qb_creating_bill", extra={
        "tenant_id": tenant_id, "vendor_id": vendor_id,
        "account_id": account_id, "invoice_number": invoice_number,
    })
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
