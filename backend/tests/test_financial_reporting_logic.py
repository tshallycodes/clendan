"""
Unit tests for the Financial Reporting tool's pure statement math.

Covers the P&L / balance-sheet / cash-flow snapshot builder, ratio and
period-change computation, the balance-sheet reconciliation invariant
(assets = liabilities + equity), cash-flow payment classification, and
period-anomaly detection. No DB or Claude calls — all functions under test
are pure and operate on lightweight stand-in records.
"""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.tools.financial_reporting import (
    _INFLOW_PAYMENT_TYPES,
    _OUTFLOW_PAYMENT_TYPES,
    _ToolPolicy,
    _build_snapshot,
    _compute_period_changes,
    _compute_ratios,
)

# Period: a fixed 30-day window and its immediately-prior 30-day window.
P_END = datetime(2026, 6, 30, tzinfo=UTC)
P_START = P_END - timedelta(days=30)
PRIOR_END = P_START
PRIOR_START = PRIOR_END - timedelta(days=30)

IN = datetime(2026, 6, 15, tzinfo=UTC)          # inside current period
PRIOR_IN = datetime(2026, 5, 20, tzinfo=UTC)     # inside prior period
OUTSIDE = datetime(2026, 1, 1, tzinfo=UTC)       # outside both


def _inv(total, outstanding, issue_date=IN):
    return SimpleNamespace(total_cents=total, outstanding_cents=outstanding, issue_date=issue_date)


def _bill(total, outstanding, issue_date=IN):
    return SimpleNamespace(total_cents=total, outstanding_cents=outstanding, issue_date=issue_date)


def _exp(amount, expense_date=IN):
    return SimpleNamespace(amount_cents=amount, expense_date=expense_date)


def _pay(amount, ptype, paid_at=IN):
    return SimpleNamespace(amount_cents=amount, payment_type=ptype, paid_at=paid_at)


def _acct(balance):
    return SimpleNamespace(current_balance_minor=balance)


def _snapshot(**kw):
    return _build_snapshot(
        kw.get("invoices", []),
        kw.get("bills", []),
        kw.get("expenses", []),
        kw.get("payments", []),
        kw.get("bank_accounts", []),
        kw.get("p_start", P_START),
        kw.get("p_end", P_END),
    )


# ---------------------------------------------------------------------------
# Snapshot math
# ---------------------------------------------------------------------------

def test_build_snapshot_basic_pl():
    s = _snapshot(
        invoices=[_inv(100_00, 40_00), _inv(50_00, 0)],
        bills=[_bill(30_00, 10_00)],
        expenses=[_exp(20_00)],
        bank_accounts=[_acct(200_00)],
    )
    assert s.revenue_cents == 150_00           # 100 + 50
    assert s.cogs_cents == 30_00               # bills issued in period
    assert s.opex_cents == 20_00               # expenses in period
    assert s.gross_profit_cents == 120_00      # 150 - 30
    assert s.net_profit_cents == 100_00        # 120 - 20
    assert s.outstanding_ar_cents == 40_00     # only the invoice with outstanding > 0
    assert s.outstanding_ap_cents == 10_00


def test_balance_sheet_reconciles():
    """Invariant: total_assets = total_liabilities + net_assets (equity)."""
    s = _snapshot(
        invoices=[_inv(100_00, 40_00)],
        bills=[_bill(30_00, 25_00)],
        bank_accounts=[_acct(500_00), _acct(100_00)],
    )
    assert s.total_bank_balance_cents == 600_00
    assert s.total_assets_cents == s.total_bank_balance_cents + s.outstanding_ar_cents
    assert s.total_liabilities_cents == s.outstanding_ap_cents
    # The core accounting identity must hold exactly, in integer minor units.
    assert s.total_assets_cents == s.total_liabilities_cents + s.net_assets_cents


def test_cash_flow_classifies_received_and_made():
    """Regression: inflows come from 'received', outflows from 'made'.

    Previously the tool matched 'receipt'/'payment', which no integration
    ever writes, so cash flow was always zero.
    """
    s = _snapshot(
        payments=[
            _pay(80_00, "received"),
            _pay(20_00, "received"),
            _pay(30_00, "made"),
        ],
    )
    assert s.cash_inflows_cents == 100_00
    assert s.cash_outflows_cents == 30_00
    assert s.net_cash_cents == 70_00


def test_cash_flow_ignores_legacy_wrong_types():
    """The pre-fix literals must NOT be counted (guards against regression)."""
    s = _snapshot(payments=[_pay(99_00, "receipt"), _pay(99_00, "payment")])
    assert s.cash_inflows_cents == 0
    assert s.cash_outflows_cents == 0


def test_canonical_payment_type_constants():
    assert _INFLOW_PAYMENT_TYPES == frozenset({"received"})
    assert _OUTFLOW_PAYMENT_TYPES == frozenset({"made"})


def test_out_of_period_flows_excluded():
    s = _snapshot(
        invoices=[_inv(100_00, 0, issue_date=OUTSIDE)],
        bills=[_bill(50_00, 0, issue_date=OUTSIDE)],
        expenses=[_exp(10_00, expense_date=OUTSIDE)],
        payments=[_pay(10_00, "received", paid_at=OUTSIDE)],
    )
    assert s.revenue_cents == 0
    assert s.cogs_cents == 0
    assert s.opex_cents == 0
    assert s.cash_inflows_cents == 0


def test_none_dates_do_not_crash_and_are_excluded():
    s = _snapshot(
        invoices=[_inv(100_00, 5_00, issue_date=None)],
        expenses=[_exp(10_00, expense_date=None)],
        payments=[_pay(10_00, "received", paid_at=None)],
    )
    assert s.revenue_cents == 0          # None issue_date excluded from period revenue
    assert s.opex_cents == 0
    assert s.cash_inflows_cents == 0
    assert s.outstanding_ar_cents == 5_00  # outstanding is date-independent


def test_all_monetary_fields_are_integers():
    """Currency must be integer minor units — never float."""
    s = _snapshot(
        invoices=[_inv(100_00, 40_00)],
        bills=[_bill(33_00, 11_00)],
        expenses=[_exp(7_00)],
        payments=[_pay(50_00, "received"), _pay(20_00, "made")],
        bank_accounts=[_acct(500_00)],
    )
    for field in (
        "revenue_cents", "outstanding_ar_cents", "cogs_cents", "opex_cents",
        "outstanding_ap_cents", "gross_profit_cents", "net_profit_cents",
        "total_bank_balance_cents", "total_assets_cents", "total_liabilities_cents",
        "net_assets_cents", "cash_inflows_cents", "cash_outflows_cents", "net_cash_cents",
    ):
        assert isinstance(getattr(s, field), int), f"{field} must be int"


# ---------------------------------------------------------------------------
# Ratios
# ---------------------------------------------------------------------------

def test_compute_ratios_nominal():
    s = _snapshot(
        invoices=[_inv(100_00, 0)],
        bills=[_bill(40_00, 20_00)],
        expenses=[_exp(10_00)],
        bank_accounts=[_acct(80_00)],
    )
    r = _compute_ratios(s)
    assert r["gross_margin_pct"] == 60.0            # (100-40)/100
    assert r["net_margin_pct"] == 50.0             # net 50 / 100
    assert r["current_ratio"] == round(80_00 / 20_00, 4)


def test_compute_ratios_zero_revenue_and_zero_ap():
    s = _snapshot(bank_accounts=[_acct(10_00)])
    r = _compute_ratios(s)
    assert r["gross_margin_pct"] == 0
    assert r["net_margin_pct"] == 0
    assert r["current_ratio"] is None   # no AP → undefined, not a divide-by-zero


# ---------------------------------------------------------------------------
# Period changes + anomaly detection
# ---------------------------------------------------------------------------

def test_compute_period_changes():
    cur = _snapshot(invoices=[_inv(150_00, 0)], bills=[_bill(30_00, 0)], expenses=[_exp(20_00)])
    prior = _snapshot(
        invoices=[_inv(100_00, 0, issue_date=PRIOR_IN)],
        bills=[_bill(30_00, 0, issue_date=PRIOR_IN)],
        expenses=[_exp(20_00, expense_date=PRIOR_IN)],
        p_start=PRIOR_START, p_end=PRIOR_END,
    )
    pc = _compute_period_changes(cur, prior)
    assert pc["prior_period_revenue_minor"] == 100_00
    assert pc["revenue_change_pct"] == 50.0                # (150-100)/100
    assert pc["expense_change_pct"] == 0.0                 # 50 vs 50
    assert pc["prior_period_expenses_minor"] == 50_00      # cogs 30 + opex 20


def test_period_change_none_on_zero_prior():
    cur = _snapshot(invoices=[_inv(50_00, 0)])
    prior = _snapshot(p_start=PRIOR_START, p_end=PRIOR_END)  # empty prior
    pc = _compute_period_changes(cur, prior)
    assert pc["revenue_change_pct"] is None                 # no divide-by-zero


def test_period_anomaly_threshold_logic():
    """Mirrors the inline detection in _execute: flag keys whose |change| exceeds threshold."""
    policy = _ToolPolicy(lookback_days=30, anomaly_variance_pct=0.25)  # 25%
    period_changes = {
        "revenue_change_pct": 50.0,     # exceeds 25 -> flagged
        "expense_change_pct": 10.0,     # within 25 -> not flagged
        "net_income_change_pct": -40.0, # abs exceeds 25 -> flagged
    }
    threshold = policy.anomaly_variance_pct * 100
    flagged = [
        k for k in ("revenue_change_pct", "expense_change_pct", "net_income_change_pct")
        if (v := period_changes.get(k)) is not None and abs(v) > threshold
    ]
    assert flagged == ["revenue_change_pct", "net_income_change_pct"]
