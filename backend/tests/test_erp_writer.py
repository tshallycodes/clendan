"""
Tests for the integration-agnostic ERP write rail (app/core/erp_writer.py) and the
provider writers' pure mapping helpers. No network - settings, the Prisma client and the
provider write functions are mocked.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _settings(live: bool):
    s = MagicMock()
    s.erp_write_live = live
    return s


def _integration(type_="quickbooks", id_="erp1"):
    m = MagicMock()
    m.id = id_
    m.type = type_
    return m


def _db(integration=None):
    db = MagicMock()
    db.integration.find_first = AsyncMock(return_value=integration)
    db.accountingbill.update = AsyncMock()
    db.journalentry.update = AsyncMock()
    db.journalentryline.find_many = AsyncMock(return_value=[])
    return db


def _bill():
    b = MagicMock()
    b.id = "bill1"
    b.raw_data = None
    b.contact_name = "Acme"
    b.number = "INV-1"
    b.total_cents = 12_000
    b.currency = "GBP"
    b.due_date = None
    b.source = "invoice"
    b.integration_id = None
    return b


def _line(debit=0, credit=0, code="400", name="Rent"):
    m = MagicMock()
    m.debit_minor = debit
    m.credit_minor = credit
    m.account_code = code
    m.account_name = name
    m.description = "d"
    return m


# ---- rail: dry-run ----------------------------------------------------------

@pytest.mark.asyncio
async def test_post_bill_dry_run_changes_nothing():
    db = _db(_integration("quickbooks"))
    with patch("app.core.erp_writer.get_settings", return_value=_settings(False)):
        from app.core.erp_writer import post_bill
        res = await post_bill(db, "t1", _bill())
    assert res["mode"] == "dry_run"
    assert res["provider"] == "quickbooks"
    db.accountingbill.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_post_journal_dry_run_changes_nothing():
    db = _db(_integration("xero"))
    entry = MagicMock(id="je1", description="Accrual", currency="GBP")
    with patch("app.core.erp_writer.get_settings", return_value=_settings(False)):
        from app.core.erp_writer import post_journal_entry
        res = await post_journal_entry(db, "t1", entry)
    assert res["mode"] == "dry_run"
    db.journalentry.update.assert_not_awaited()


# ---- rail: live guards ------------------------------------------------------

@pytest.mark.asyncio
async def test_post_bill_live_without_erp_raises():
    db = _db(None)
    with patch("app.core.erp_writer.get_settings", return_value=_settings(True)):
        from app.core.erp_writer import post_bill, ErpWriteError
        with pytest.raises(ErpWriteError, match="no accounting integration"):
            await post_bill(db, "t1", _bill())


@pytest.mark.asyncio
async def test_post_journal_live_without_lines_raises():
    db = _db(_integration("quickbooks"))
    db.journalentryline.find_many = AsyncMock(return_value=[])
    entry = MagicMock(id="je1", description="x", currency="GBP")
    with patch("app.core.erp_writer.get_settings", return_value=_settings(True)):
        from app.core.erp_writer import post_journal_entry, ErpWriteError
        with pytest.raises(ErpWriteError, match="no lines"):
            await post_journal_entry(db, "t1", entry)


# ---- rail: live dispatch + Clendan-side linkage -----------------------------

@pytest.mark.asyncio
async def test_post_bill_live_quickbooks_links_external_id():
    db = _db(_integration("quickbooks"))
    with (
        patch("app.core.erp_writer.get_settings", return_value=_settings(True)),
        patch("app.integrations.quickbooks.write.write_bill_to_quickbooks",
              AsyncMock(return_value={"qb_bill_id": "QB9"})) as w,
    ):
        from app.core.erp_writer import post_bill
        res = await post_bill(db, "t1", _bill(), execution_id="e1")
    w.assert_awaited_once()
    assert res == {"mode": "live", "provider": "quickbooks", "bill_id": "bill1", "external_id": "QB9"}
    data = db.accountingbill.update.await_args.kwargs["data"]
    assert data["integration_id"] == "erp1" and data["external_id"] == "QB9"


@pytest.mark.asyncio
async def test_post_bill_live_xero_dispatches():
    db = _db(_integration("xero"))
    with (
        patch("app.core.erp_writer.get_settings", return_value=_settings(True)),
        patch("app.integrations.xero.write.create_bill",
              AsyncMock(return_value={"external_id": "XR1"})) as w,
    ):
        from app.core.erp_writer import post_bill
        res = await post_bill(db, "t1", _bill())
    w.assert_awaited_once()
    assert res["provider"] == "xero" and res["external_id"] == "XR1"


@pytest.mark.asyncio
async def test_post_journal_live_quickbooks_marks_posted():
    db = _db(_integration("quickbooks"))
    db.journalentryline.find_many = AsyncMock(return_value=[_line(debit=5000), _line(credit=5000)])
    entry = MagicMock(id="je1", description="Accrual", currency="GBP")
    with (
        patch("app.core.erp_writer.get_settings", return_value=_settings(True)),
        patch("app.integrations.quickbooks.write.write_journal_to_quickbooks",
              AsyncMock(return_value={"qb_journal_id": "J7"})) as w,
    ):
        from app.core.erp_writer import post_journal_entry
        res = await post_journal_entry(db, "t1", entry)
    w.assert_awaited_once()
    assert res["external_id"] == "J7"
    data = db.journalentry.update.await_args.kwargs["data"]
    assert data["status"] == "posted" and data["external_id"] == "J7" and data["posted_at"] is not None


# ---- pure mapping helpers ---------------------------------------------------

def test_lines_payload_maps_debit_and_credit():
    from app.core.erp_writer import _lines_payload
    payload = _lines_payload([_line(debit=5000, code="400", name="Rent"),
                              _line(credit=5000, code="800", name="Bank")])
    assert payload[0] == {"account_code": "400", "account_name": "Rent",
                          "posting_type": "Debit", "amount_minor": 5000, "description": "d"}
    assert payload[1]["posting_type"] == "Credit" and payload[1]["amount_minor"] == 5000


def test_resolve_prefers_preferred_id():
    from app.core.erp_writer import resolve_erp_integration
    import asyncio
    preferred = _integration("xero", "pref")
    db = _db(preferred)
    got = asyncio.get_event_loop().run_until_complete(
        resolve_erp_integration(db, "t1", preferred_id="pref")
    )
    assert got is preferred
    where = db.integration.find_first.await_args.kwargs["where"]
    assert where["id"] == "pref" and where["tenant_id"] == "t1"


# ---- provider mapping: QB journal account resolution ------------------------

@pytest.mark.asyncio
async def test_qb_journal_resolves_accounts_and_raises_on_unmapped():
    from app.integrations.quickbooks import write as qbwrite
    accounts = [{"Id": "10", "AcctNum": "400", "Name": "Rent"},
                {"Id": "20", "AcctNum": "800", "Name": "Bank"}]
    with (
        patch.object(qbwrite, "_load_qb_credentials", AsyncMock(return_value=("acc", "realm", True))),
        patch("app.integrations.quickbooks.client.get_accounts", AsyncMock(return_value=accounts)),
        patch("app.integrations.quickbooks.client.create_journal_entry",
              AsyncMock(return_value={"qb_journal_id": "J1"})) as create,
    ):
        # by account number
        await qbwrite.write_journal_to_quickbooks(
            "t1", description="x",
            lines=[{"account_code": "400", "account_name": "Rent", "posting_type": "Debit", "amount_minor": 100, "description": ""}],
        )
        qb_lines = create.await_args.kwargs["lines"]
        assert qb_lines[0]["account_id"] == "10"

        # unmapped account -> raise, never post a wrong entry
        with pytest.raises(ValueError, match="Cannot map"):
            await qbwrite.write_journal_to_quickbooks(
                "t1", description="x",
                lines=[{"account_code": "999", "account_name": "Nope", "posting_type": "Credit", "amount_minor": 100}],
            )


# ---- provider mapping: Xero manual-journal signing --------------------------

def test_xero_manual_journal_signs_debit_positive_credit_negative():
    from app.integrations.xero.write import _manual_journal_lines
    out = _manual_journal_lines([
        {"account_code": "400", "posting_type": "Debit", "amount_minor": 5000, "description": "rent"},
        {"account_code": "800", "posting_type": "Credit", "amount_minor": 5000, "description": ""},
    ])
    assert out[0]["LineAmount"] == 50.0 and out[0]["AccountCode"] == "400"
    assert out[1]["LineAmount"] == -50.0  # credit is negative in Xero
