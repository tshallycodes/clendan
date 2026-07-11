"""
ERP report pull-through. Read the customer's *authoritative* P&L / balance-sheet / VAT
figures from the connected accounting system (QuickBooks / Xero) instead of re-deriving them.
This is the operator model: operate their numbers, don't reinvent the ledger.

Read-only and best-effort: ``fetch_report`` returns the raw ERP report, or None when no
connected source exposes that report. Callers (the /reports endpoints, and later the tools)
fall back to Clendan's own computation when it returns None - which is why the compute engines
in tax_compliance / financial_reporting are kept.
"""
from __future__ import annotations

from app.core.logging import get_logger

logger = get_logger(__name__)

_REPORT_PROVIDERS = ("quickbooks", "xero")

# Canonical report_type -> provider-specific report name. A missing entry => that provider
# does not expose that report via its Reports API (caller falls back).
_QB_REPORTS = {"pnl": "ProfitAndLoss", "balance_sheet": "BalanceSheet", "vat": "VATDetailReport"}
_XERO_REPORTS = {"pnl": "ProfitAndLoss", "balance_sheet": "BalanceSheet"}  # Xero VAT isn't a Reports endpoint


class ErpReportError(Exception):
    """Raised when a report fetch is attempted but fails hard (auth, network)."""


async def resolve_report_integration(db, tenant_id: str, preferred_id: str | None = None):
    """Return a connected report-capable ERP (QuickBooks/Xero) for the tenant, or None."""
    base = {"tenant_id": tenant_id, "type": {"in": list(_REPORT_PROVIDERS)}}
    if preferred_id:
        intg = await db.integration.find_first(where={**base, "id": preferred_id})
        if intg:
            return intg
    return await db.integration.find_first(
        where={**base, "connected_at": {"not": None}},
        order={"connected_at": "desc"},
    )


async def fetch_report(
    db, tenant_id: str, report_type: str, *, preferred_integration_id: str | None = None,
) -> dict | None:
    """Fetch the ERP's authoritative report of ``report_type`` (pnl | balance_sheet | vat).

    Returns ``{"source", "report_type", "report_name", "raw"}`` or None when no connected ERP
    exposes it (the caller then falls back to Clendan's own computation).
    """
    intg = await resolve_report_integration(db, tenant_id, preferred_integration_id)
    if intg is None:
        return None

    if intg.type == "quickbooks":
        name = _QB_REPORTS.get(report_type)
        if not name:
            return None
        from app.integrations.quickbooks import client as qb
        from app.integrations.quickbooks.write import _load_qb_credentials
        access, realm, sandbox = await _load_qb_credentials(db, tenant_id)
        raw = await qb.get_report(access, realm, name, sandbox=sandbox)
        return {"source": "quickbooks", "report_type": report_type, "report_name": name, "raw": raw}

    if intg.type == "xero":
        name = _XERO_REPORTS.get(report_type)
        if not name:
            return None
        from app.integrations.xero import client_api as xero_api
        from app.integrations.xero.write import _xero_context
        access, xero_tenant_id = await _xero_context(db, tenant_id, intg)
        raw = await xero_api.get_report(access, xero_tenant_id, name)
        return {"source": "xero", "report_type": report_type, "report_name": name, "raw": raw}

    return None
