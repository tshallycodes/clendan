"""
Unit tests for the tax_compliance tool's deterministic building blocks.

Covers the VAT position computation (integer minor units, never float),
missing-tax-code detection, filing-period detection, payload validation, and
policy parsing. No DB or Claude calls — pure functions only.
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.tools.tax_compliance import (
    _coerce_lookback_days,
    _compute_vat_position,
    _detect_filing_period,
    _flag_missing_tax,
    _parse_policy,
    _persist_tax_classifications,
    _persist_vat_return,
)


def _invoice(id: str, tax_cents: int, total_cents: int) -> SimpleNamespace:
    # AccountingInvoice persists tax_cents + total_cents.
    return SimpleNamespace(id=id, tax_cents=tax_cents, total_cents=total_cents)


def _expense(id: str, tax_cents: int, amount_cents: int) -> SimpleNamespace:
    # AccountingExpense persists tax_cents + amount_cents (no total_cents).
    return SimpleNamespace(id=id, tax_cents=tax_cents, amount_cents=amount_cents)


def _bill(id: str, total_cents: int, tax_cents: int = 0) -> SimpleNamespace:
    # AccountingBill now persists tax_cents (populated by the ERP sync); native bills default 0.
    return SimpleNamespace(id=id, total_cents=total_cents, tax_cents=tax_cents)


# ---------------------------------------------------------------------------
# _flag_missing_tax — missing-tax-code detection
# ---------------------------------------------------------------------------

def test_flag_missing_tax_flags_zero_tax_above_threshold():
    rows = [_invoice("inv_1", tax_cents=0, total_cents=50_000)]
    flagged = _flag_missing_tax(rows, threshold_cents=10_000)
    assert flagged == [{"id": "inv_1", "total_cents": 50_000}]


def test_flag_missing_tax_ignores_zero_tax_below_threshold():
    rows = [_invoice("inv_1", tax_cents=0, total_cents=9_999)]
    assert _flag_missing_tax(rows, threshold_cents=10_000) == []


def test_flag_missing_tax_ignores_records_with_tax():
    rows = [_invoice("inv_1", tax_cents=2_000, total_cents=50_000)]
    assert _flag_missing_tax(rows, threshold_cents=10_000) == []


def test_flag_missing_tax_threshold_is_inclusive():
    rows = [_invoice("inv_1", tax_cents=0, total_cents=10_000)]
    assert _flag_missing_tax(rows, threshold_cents=10_000) == [
        {"id": "inv_1", "total_cents": 10_000}
    ]


def test_flag_missing_tax_uses_amount_cents_for_expenses():
    rows = [_expense("exp_1", tax_cents=0, amount_cents=25_000)]
    assert _flag_missing_tax(rows, threshold_cents=10_000) == [
        {"id": "exp_1", "total_cents": 25_000}
    ]


def test_flag_missing_tax_skips_records_without_tax_field():
    # A record whose model carries no tax figure at all (getattr -> None) is skipped: an
    # absent field is not evidence of missing tax. (Bills now carry tax_cents, so they
    # participate - this guards any future model that does not.)
    no_tax = [SimpleNamespace(id="x1", total_cents=1_000_000)]
    assert _flag_missing_tax(no_tax, threshold_cents=10_000) == []


def test_flag_missing_tax_flags_bills_with_zero_tax():
    # Bills now persist tax_cents; a 0-tax bill above the threshold is a genuine missing-tax signal.
    bills = [_bill("bill_1", total_cents=1_000_000, tax_cents=0)]
    assert _flag_missing_tax(bills, threshold_cents=10_000) == [{"id": "bill_1", "total_cents": 1_000_000}]


def test_flag_missing_tax_mixed_rows():
    rows = [
        _invoice("inv_1", tax_cents=0, total_cents=20_000),   # flagged
        _invoice("inv_2", tax_cents=500, total_cents=20_000),  # has tax
        _invoice("inv_3", tax_cents=0, total_cents=5_000),     # below threshold
    ]
    assert _flag_missing_tax(rows, threshold_cents=10_000) == [
        {"id": "inv_1", "total_cents": 20_000}
    ]


# ---------------------------------------------------------------------------
# _compute_vat_position — deterministic integer VAT math
# ---------------------------------------------------------------------------

def test_compute_vat_position_basic():
    invoices = [_invoice("i1", 2_000, 12_000), _invoice("i2", 3_000, 18_000)]
    bills = [_bill("b1", 6_000)]  # 0 tax → contributes 0
    expenses = [_expense("e1", 1_000, 5_000)]
    output_vat, input_vat, net = _compute_vat_position(invoices, bills, expenses)
    assert output_vat == 5_000        # 2_000 + 3_000
    assert input_vat == 1_000         # bill contributes 0, expense 1_000
    assert net == 4_000               # 5_000 - 1_000


def test_compute_vat_position_returns_integers():
    invoices = [_invoice("i1", 2_000, 12_000)]
    output_vat, input_vat, net = _compute_vat_position(invoices, [], [])
    assert all(isinstance(v, int) for v in (output_vat, input_vat, net))


def test_compute_vat_position_negative_net_is_reclaim():
    # More input VAT than output → net negative (a reclaim/refund position).
    invoices = [_invoice("i1", 1_000, 6_000)]
    expenses = [_expense("e1", 4_000, 24_000)]
    _, _, net = _compute_vat_position(invoices, [], expenses)
    assert net == -3_000


def test_compute_vat_position_empty():
    assert _compute_vat_position([], [], []) == (0, 0, 0)


def test_compute_vat_position_bills_contribute_input_vat():
    # Bills now carry tax_cents (populated by the ERP sync) and add to reclaimable input VAT.
    bills = [_bill("b1", 60_000, tax_cents=10_000)]
    output_vat, input_vat, net = _compute_vat_position([], bills, [])
    assert (output_vat, input_vat, net) == (0, 10_000, -10_000)


# ---------------------------------------------------------------------------
# _detect_filing_period
# ---------------------------------------------------------------------------

_REF = datetime(2026, 7, 7)  # Q3


def test_detect_filing_period_monthly():
    assert _detect_filing_period(30, _REF) == ("monthly", "July 2026")


def test_detect_filing_period_quarterly():
    assert _detect_filing_period(90, _REF) == ("quarterly", "Q3 2026")


def test_detect_filing_period_annual():
    assert _detect_filing_period(365, _REF) == ("annual", "2026")


# ---------------------------------------------------------------------------
# _coerce_lookback_days — untrusted payload validation
# ---------------------------------------------------------------------------

def test_coerce_lookback_days_valid():
    assert _coerce_lookback_days(45) == 45


def test_coerce_lookback_days_numeric_string():
    assert _coerce_lookback_days("60") == 60


def test_coerce_lookback_days_rejects_negative():
    assert _coerce_lookback_days(-5) == 90


def test_coerce_lookback_days_rejects_zero():
    assert _coerce_lookback_days(0) == 90


def test_coerce_lookback_days_rejects_non_numeric():
    assert _coerce_lookback_days("abc") == 90
    assert _coerce_lookback_days(None) == 90


def test_coerce_lookback_days_clamps_upper_bound():
    assert _coerce_lookback_days(999_999) == 3660


# ---------------------------------------------------------------------------
# _parse_policy
# ---------------------------------------------------------------------------

def test_parse_policy_defaults():
    policy = _parse_policy({})
    assert policy.vat_alert_threshold_cents == 1_000_000
    assert policy.missing_tax_flag_threshold_cents == 10_000


def test_parse_policy_flat_config():
    policy = _parse_policy(
        {"vat_alert_threshold_cents": 500_000, "missing_tax_flag_threshold_cents": 25_000}
    )
    assert policy.vat_alert_threshold_cents == 500_000
    assert policy.missing_tax_flag_threshold_cents == 25_000


def test_parse_policy_nested_policy_key():
    policy = _parse_policy({"policy": {"vat_alert_threshold_cents": 750_000}})
    assert policy.vat_alert_threshold_cents == 750_000


def test_parse_policy_ignores_unknown_keys():
    policy = _parse_policy({"vat_alert_threshold_cents": 123, "junk": "ignored"})
    assert policy.vat_alert_threshold_cents == 123


# ---------------------------------------------------------------------------
# _persist_tax_classifications — missing-VAT writeback
# ---------------------------------------------------------------------------

def _wb_db():
    db = MagicMock()
    db.accountinginvoice.update_many = AsyncMock()
    db.accountingbill.update_many = AsyncMock()
    db.accountingexpense.update_many = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_persist_tax_classifications_routes_by_table():
    db = _wb_db()
    items = [
        {"id": "inv1", "classification": "missing_vat", "reason": "should charge VAT"},
        {"id": "bill1", "classification": "exempt", "reason": "financial services"},
        {"id": "exp1", "classification": "zero_rated", "reason": "exports"},
        {"id": "ghost", "classification": "missing_vat", "reason": "x"},  # not in any set -> skipped
    ]
    counts = await _persist_tax_classifications(db, "t1", items, ["inv1"], ["bill1"], ["exp1"])
    assert counts == {"invoices": 1, "bills": 1, "expenses": 1}
    inv_call = db.accountinginvoice.update_many.await_args.kwargs
    assert inv_call["where"] == {"id": "inv1", "tenant_id": "t1"}  # tenant-scoped
    assert inv_call["data"]["tax_status"] == "missing_vat"


@pytest.mark.asyncio
async def test_persist_tax_classifications_skips_incomplete_items():
    db = _wb_db()
    items = [{"id": "inv1"}, {"classification": "missing_vat"}]  # missing class / missing id
    counts = await _persist_tax_classifications(db, "t1", items, ["inv1"], [], [])
    assert counts == {"invoices": 0, "bills": 0, "expenses": 0}
    db.accountinginvoice.update_many.assert_not_awaited()


# ---------------------------------------------------------------------------
# _persist_vat_return — the VAT-return artifact
# ---------------------------------------------------------------------------

def _vr_kwargs():
    return dict(filing_period="quarterly", period_label="Q3 2026",
                output_vat=5000, input_vat=1000, net_vat=4000, currency="GBP", missing_vat_count=2)


@pytest.mark.asyncio
async def test_persist_vat_return_creates_when_absent():
    db = MagicMock()
    db.vatreturn.find_first = AsyncMock(return_value=None)
    db.vatreturn.create = AsyncMock(return_value=MagicMock(id="vr1"))
    db.vatreturn.update = AsyncMock()
    rid = await _persist_vat_return(db, "t1", "e1", **_vr_kwargs())
    assert rid == "vr1"
    db.vatreturn.create.assert_awaited_once()
    db.vatreturn.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_persist_vat_return_updates_existing_draft():
    db = MagicMock()
    db.vatreturn.find_first = AsyncMock(return_value=MagicMock(id="vr1", status="draft"))
    db.vatreturn.create = AsyncMock()
    db.vatreturn.update = AsyncMock()
    rid = await _persist_vat_return(db, "t1", "e1", **_vr_kwargs())
    assert rid == "vr1"
    db.vatreturn.update.assert_awaited_once()
    db.vatreturn.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_persist_vat_return_never_overwrites_filed():
    db = MagicMock()
    db.vatreturn.find_first = AsyncMock(return_value=MagicMock(id="vr1", status="filed"))
    db.vatreturn.create = AsyncMock()
    db.vatreturn.update = AsyncMock()
    rid = await _persist_vat_return(db, "t1", "e1", **_vr_kwargs())
    assert rid == "vr1"
    db.vatreturn.update.assert_not_awaited()  # a filed return is immutable to later runs
    db.vatreturn.create.assert_not_awaited()
