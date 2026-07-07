"""
Unit tests for reconciliation pure logic — the deterministic helpers that decide
whether a bank transaction matches an invoice/bill, the currency-safety guard, the
policy parsing (frontend-key remapping + percentage conversion), the pre-classify
fast path, and the item fingerprint used for cache keys. No DB or Claude calls.
"""
from datetime import UTC, datetime, timedelta

from app.tools.reconciliation import (
    _AUTO_OK_THRESHOLD_MINOR,
    _MAX_CLAUDE_TXN_ITEMS,
    _amounts_match,
    _currency_matches,
    _dates_match,
    _item_fingerprint,
    _parse_policy,
    _pre_classify,
    _TransactionRecord,
)


def _txn(**overrides) -> _TransactionRecord:
    defaults = dict(
        id="txn1",
        tenant_id="t1",
        account_id="acc1",
        amount_minor=5_000,
        currency="GBP",
        merchant_name="Acme",
        description="payment",
        date=datetime.now(UTC),
        status="pending",
    )
    defaults.update(overrides)
    return _TransactionRecord(**defaults)


# ── _amounts_match ────────────────────────────────────────────────────────────

def test_amounts_match_exact():
    assert _amounts_match(1000, 1000, 150) is True


def test_amounts_match_within_tolerance():
    assert _amounts_match(1000, 1100, 150) is True  # diff 100 <= 150


def test_amounts_match_outside_tolerance():
    assert _amounts_match(1000, 1200, 150) is False  # diff 200 > 150


def test_amounts_match_zero_outstanding_requires_zero_txn():
    assert _amounts_match(0, 0, 150) is True
    assert _amounts_match(100, 0, 150) is False


# ── _dates_match ──────────────────────────────────────────────────────────────

def test_dates_match_within_window():
    d = datetime(2026, 1, 10, tzinfo=UTC)
    assert _dates_match(d, d + timedelta(days=3), 5) is True


def test_dates_match_outside_window():
    d = datetime(2026, 1, 10, tzinfo=UTC)
    assert _dates_match(d, d + timedelta(days=10), 5) is False


def test_dates_match_none_due_date_is_permissive():
    assert _dates_match(datetime.now(UTC), None, 5) is True


# ── _currency_matches (currency-safety guard) ─────────────────────────────────

def test_currency_matches_same():
    assert _currency_matches("GBP", "GBP") is True


def test_currency_matches_case_insensitive():
    assert _currency_matches("gbp", "GBP") is True


def test_currency_matches_different_is_false():
    assert _currency_matches("GBP", "EUR") is False


def test_currency_matches_none_vs_value_is_false():
    assert _currency_matches(None, "GBP") is False
    assert _currency_matches("GBP", None) is False


# ── _parse_policy ─────────────────────────────────────────────────────────────

def test_parse_policy_percentage_converted_to_fraction():
    p = _parse_policy({"unmatched_pct_threshold": 20})
    assert p.unmatched_pct_threshold == 0.20


def test_parse_policy_fraction_left_as_is():
    p = _parse_policy({"unmatched_pct_threshold": 0.2})
    assert p.unmatched_pct_threshold == 0.2


def test_parse_policy_frontend_key_remapping():
    p = _parse_policy({"amount_tolerance_minor_units": 300, "date_tolerance_days": 7})
    assert p.match_amount_tolerance_minor == 300
    assert p.match_date_window_days == 7


def test_parse_policy_overrides_win():
    p = _parse_policy({"match_date_window_days": 5}, overrides={"match_date_window_days": 2})
    assert p.match_date_window_days == 2


def test_parse_policy_defaults_when_empty():
    p = _parse_policy({})
    assert p.unmatched_pct_threshold == 0.20
    assert p.match_amount_tolerance_minor == 150


# ── _pre_classify ─────────────────────────────────────────────────────────────

def test_pre_classify_below_threshold_is_auto_ok():
    small = _txn(id="s", amount_minor=_AUTO_OK_THRESHOLD_MINOR - 1)
    needs_claude, auto = _pre_classify([small])
    assert needs_claude == []
    assert len(auto) == 1
    assert auto[0].item_id == "s" and auto[0].action == "ok"


def test_pre_classify_above_threshold_goes_to_claude():
    big = _txn(id="b", amount_minor=_AUTO_OK_THRESHOLD_MINOR + 10_000)
    needs_claude, auto = _pre_classify([big])
    assert [t.id for t in needs_claude] == ["b"]
    assert auto == []


def test_pre_classify_caps_at_max_and_sorts_by_amount_desc():
    # More than the cap, all above threshold — only the top-N by |amount| go to Claude.
    txns = [
        _txn(id=f"t{i}", amount_minor=_AUTO_OK_THRESHOLD_MINOR + i * 100)
        for i in range(_MAX_CLAUDE_TXN_ITEMS + 5)
    ]
    needs_claude, auto = _pre_classify(txns)
    assert len(needs_claude) == _MAX_CLAUDE_TXN_ITEMS
    assert len(auto) == 5
    # Highest amount first
    amounts = [t.amount_minor for t in needs_claude]
    assert amounts == sorted(amounts, reverse=True)
    # The smallest 5 (above threshold) fell to the auto-ok tail
    assert all(a.action == "ok" for a in auto)


# ── _item_fingerprint ─────────────────────────────────────────────────────────

def test_item_fingerprint_stable_and_sensitive():
    a = _item_fingerprint("5000", "pending", "Acme", "desc")
    b = _item_fingerprint("5000", "pending", "Acme", "desc")
    c = _item_fingerprint("5001", "pending", "Acme", "desc")
    assert a == b
    assert a != c


def test_item_fingerprint_handles_none():
    # None parts must not raise and must be stable
    assert _item_fingerprint(None, "x") == _item_fingerprint(None, "x")
