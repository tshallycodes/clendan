import pytest
from app.policy.engine import Decision, evaluate_policy


BASE = dict(
    verified_suppliers=["Acme Corp", "Trusted Vendor"],
    allowed_currencies=["GBP", "USD", "EUR"],
    auto_threshold_minor=50_000,    # £500
    block_threshold_minor=1_000_000, # £10,000
)


def _eval(**overrides):
    kwargs = dict(
        amount_minor=10_000,
        currency="GBP",
        vendor="Acme Corp",
        **BASE,
    )
    kwargs.update(overrides)
    return evaluate_policy(**kwargs)


# --- Currency rule ---

def test_blocked_currency_not_in_allowlist():
    result = _eval(currency="JPY")
    assert result.decision == Decision.BLOCKED
    assert result.rule_triggered == "currency_allowlist"


def test_allowed_currency_passes():
    result = _eval(currency="USD")
    assert result.decision == Decision.AUTO_APPROVED


# --- Amount block threshold ---

def test_blocked_above_block_threshold():
    result = _eval(amount_minor=1_000_001)
    assert result.decision == Decision.BLOCKED
    assert result.rule_triggered == "amount_block_threshold"


def test_exactly_at_block_threshold_is_blocked():
    result = _eval(amount_minor=1_000_001)
    assert result.decision == Decision.BLOCKED


def test_at_block_threshold_not_exceeded_is_not_blocked():
    result = _eval(amount_minor=1_000_000)
    assert result.decision == Decision.APPROVAL_REQUIRED
    assert result.rule_triggered == "amount_approve_threshold"


# --- Amount approve threshold ---

def test_approval_required_above_auto_threshold():
    result = _eval(amount_minor=50_001)
    assert result.decision == Decision.APPROVAL_REQUIRED
    assert result.rule_triggered == "amount_approve_threshold"


def test_exactly_at_auto_threshold_is_auto_approved():
    result = _eval(amount_minor=50_000)
    assert result.decision == Decision.AUTO_APPROVED


# --- Supplier rule ---

def test_approval_required_unverified_supplier():
    result = _eval(vendor="Unknown Supplier")
    assert result.decision == Decision.APPROVAL_REQUIRED
    assert result.rule_triggered == "verified_supplier"


def test_verified_supplier_passes():
    result = _eval(vendor="Trusted Vendor")
    assert result.decision == Decision.AUTO_APPROVED


# --- Auto-approve (all pass) ---

def test_auto_approved_all_rules_pass():
    result = _eval(amount_minor=100, currency="GBP", vendor="Acme Corp")
    assert result.decision == Decision.AUTO_APPROVED
    assert result.rule_triggered == "none"


# --- Rule priority: currency checked before amount ---

def test_currency_blocked_before_amount_checked():
    result = _eval(currency="JPY", amount_minor=2_000_000)
    assert result.decision == Decision.BLOCKED
    assert result.rule_triggered == "currency_allowlist"


# --- Rule priority: amount block checked before supplier ---

def test_amount_block_before_supplier_check():
    result = _eval(amount_minor=2_000_000, vendor="Unknown Supplier")
    assert result.decision == Decision.BLOCKED
    assert result.rule_triggered == "amount_block_threshold"


# --- Empty verified_suppliers list ---

def test_empty_verified_suppliers_always_requires_approval():
    result = _eval(vendor="Acme Corp", verified_suppliers=[])
    assert result.decision == Decision.APPROVAL_REQUIRED
    assert result.rule_triggered == "verified_supplier"
