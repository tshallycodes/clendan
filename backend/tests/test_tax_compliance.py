"""
Unit tests for the tax_compliance tool's deterministic building blocks.

Covers the VAT position computation (integer minor units, never float),
missing-tax-code detection, filing-period detection, payload validation, and
policy parsing. No DB or Claude calls — pure functions only.
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from app.tools.tax_compliance import (
    _coerce_lookback_days,
    _compute_vat_position,
    _detect_filing_period,
    _flag_missing_tax,
    _parse_policy,
)


def _invoice(id: str, tax_cents: int, total_cents: int) -> SimpleNamespace:
    # AccountingInvoice persists tax_cents + total_cents.
    return SimpleNamespace(id=id, tax_cents=tax_cents, total_cents=total_cents)


def _expense(id: str, tax_cents: int, amount_cents: int) -> SimpleNamespace:
    # AccountingExpense persists tax_cents + amount_cents (no total_cents).
    return SimpleNamespace(id=id, tax_cents=tax_cents, amount_cents=amount_cents)


def _bill(id: str, total_cents: int) -> SimpleNamespace:
    # AccountingBill has NO tax_cents column — deliberately omitted here.
    return SimpleNamespace(id=id, total_cents=total_cents)


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
    # Regression: AccountingBill has no tax_cents column. It must NOT be flagged as
    # "missing tax" simply because the field is absent (previously all bills flagged).
    bills = [_bill("bill_1", total_cents=1_000_000), _bill("bill_2", total_cents=500_000)]
    assert _flag_missing_tax(bills, threshold_cents=10_000) == []


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
    bills = [_bill("b1", 6_000)]  # no tax_cents → contributes 0
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


def test_compute_vat_position_bills_never_contribute():
    # Even large bills add nothing to input VAT because they carry no tax figure.
    bills = [_bill("b1", 10_000_000)]
    output_vat, input_vat, net = _compute_vat_position([], bills, [])
    assert (output_vat, input_vat, net) == (0, 0, 0)


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
