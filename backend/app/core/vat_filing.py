"""
VAT return filing seam. A computed VAT return (persisted by Tax Compliance) can be filed
through this rail.

Dry-run by default (vat_filing_live False): the return is marked "prepared" with filed_at
set, but nothing is submitted to a tax authority - there is no HMRC/MTD integration yet.
Enabling vat_filing_live without a wired e-filing rail raises, so "live" never silently
no-ops. This is the seam a real MTD submission plugs into.
"""
from datetime import UTC, datetime

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class VatFilingError(Exception):
    """Raised when a live filing is requested but no e-filing rail is configured."""


async def file_vat_return(db, tenant_id: str, vat_return_id: str) -> dict:
    """File (or, in dry-run, prepare) a VAT return.

    Returns ``{"mode": "dry_run"|"noop", "status": ..., "vat_return_id": ...}``. A return
    already marked "filed" is a no-op. Tenant-scoped.
    """
    ret = await db.vatreturn.find_first(where={"id": vat_return_id, "tenant_id": tenant_id})
    if ret is None:
        raise VatFilingError(f"VAT return {vat_return_id} not found")
    if ret.status == "filed":
        return {"mode": "noop", "status": "filed", "vat_return_id": vat_return_id}

    settings = get_settings()
    if settings.vat_filing_live:
        # No HMRC/MTD e-filing integration is wired yet - refuse rather than pretend to file.
        raise VatFilingError(
            "Live VAT filing is enabled but no e-filing rail (e.g. HMRC MTD) is configured."
        )

    await db.vatreturn.update(
        where={"id": vat_return_id},
        data={"status": "prepared", "filed_at": datetime.now(UTC)},
    )
    logger.info("vat_return_prepared", extra={"tenant_id": tenant_id, "vat_return_id": vat_return_id})
    return {"mode": "dry_run", "status": "prepared", "vat_return_id": vat_return_id}
