"""
Tests for the ERP report pull-through rail (app/core/erp_reports.py). No network - the
Prisma client, credential loaders and provider report clients are mocked.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _intg(type_="quickbooks", id_="erp1"):
    m = MagicMock()
    m.id = id_
    m.type = type_
    return m


def _db(integration=None):
    db = MagicMock()
    db.integration.find_first = AsyncMock(return_value=integration)
    return db


@pytest.mark.asyncio
async def test_fetch_report_none_when_no_erp_connected():
    from app.core.erp_reports import fetch_report
    assert await fetch_report(_db(None), "t1", "pnl") is None


@pytest.mark.asyncio
async def test_fetch_report_quickbooks_pnl():
    db = _db(_intg("quickbooks"))
    with (
        patch("app.integrations.quickbooks.write._load_qb_credentials",
              AsyncMock(return_value=("acc", "realm", True))),
        patch("app.integrations.quickbooks.client.get_report",
              AsyncMock(return_value={"Header": {"ReportName": "ProfitAndLoss"}})) as gr,
    ):
        from app.core.erp_reports import fetch_report
        res = await fetch_report(db, "t1", "pnl")
    gr.assert_awaited_once()
    assert res["source"] == "quickbooks" and res["report_name"] == "ProfitAndLoss"
    assert res["raw"]["Header"]["ReportName"] == "ProfitAndLoss"


@pytest.mark.asyncio
async def test_fetch_report_xero_balance_sheet():
    db = _db(_intg("xero"))
    with (
        patch("app.integrations.xero.write._xero_context", AsyncMock(return_value=("tok", "org"))),
        patch("app.integrations.xero.client_api.get_report",
              AsyncMock(return_value={"Reports": [{"ReportID": "BalanceSheet"}]})) as gr,
    ):
        from app.core.erp_reports import fetch_report
        res = await fetch_report(db, "t1", "balance_sheet")
    gr.assert_awaited_once()
    assert res["source"] == "xero" and res["report_name"] == "BalanceSheet"


@pytest.mark.asyncio
async def test_fetch_report_xero_vat_returns_none():
    # Xero VAT is not a Reports endpoint -> None so the caller falls back to computation.
    from app.core.erp_reports import fetch_report
    assert await fetch_report(_db(_intg("xero")), "t1", "vat") is None


@pytest.mark.asyncio
async def test_fetch_report_unknown_type_none():
    from app.core.erp_reports import fetch_report
    assert await fetch_report(_db(_intg("quickbooks")), "t1", "cashflow") is None


@pytest.mark.asyncio
async def test_resolve_prefers_preferred_id_and_scopes_tenant():
    from app.core.erp_reports import resolve_report_integration
    pref = _intg("xero", "pref")
    db = _db(pref)
    got = await resolve_report_integration(db, "t1", preferred_id="pref")
    assert got is pref
    where = db.integration.find_first.await_args.kwargs["where"]
    assert where["id"] == "pref" and where["tenant_id"] == "t1"
