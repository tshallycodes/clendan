"""
Tests for evaluate_invoice_policy — the invoice-specific extension of evaluate_policy.
"""
from datetime import date, timedelta

import pytest

from app.policy.engine import Decision, evaluate_invoice_policy

BASE = dict(
    verified_suppliers=["Acme Corp"],
    allowed_currencies=["GBP", "USD", "EUR"],
    auto_threshold_minor=50_000,
    block_threshold_minor=1_000_000,
    ocr_confidence=0.95,
    min_ocr_confidence=0.85,
)


def _eval(**overrides):
    kwargs = dict(
        amount_minor=10_000,
        currency="GBP",
        vendor="Acme Corp",
        **BASE,
    )
    kwargs.update(overrides)
    return evaluate_invoice_policy(**kwargs)


# ─── OCR confidence ────────────────────────────────────────────────────────

def test_blocked_when_ocr_confidence_below_minimum():
    result = _eval(ocr_confidence=0.70, min_ocr_confidence=0.85)
    assert result.decision == Decision.BLOCKED
    assert result.rule_triggered == "ocr_confidence"


def test_blocked_exactly_at_minimum_boundary():
    result = _eval(ocr_confidence=0.849, min_ocr_confidence=0.85)
    assert result.decision == Decision.BLOCKED
    assert result.rule_triggered == "ocr_confidence"


def test_passes_when_ocr_confidence_at_minimum():
    result = _eval(ocr_confidence=0.85, min_ocr_confidence=0.85)
    assert result.decision == Decision.AUTO_APPROVED


def test_ocr_checked_before_duplicate():
    """OCR confidence is checked before duplicate detection."""
    result = _eval(ocr_confidence=0.50, is_duplicate=True)
    assert result.rule_triggered == "ocr_confidence"


# ─── Duplicate detection ───────────────────────────────────────────────────

def test_blocked_on_duplicate_invoice():
    result = _eval(is_duplicate=True)
    assert result.decision == Decision.BLOCKED
    assert result.rule_triggered == "duplicate_invoice"


def test_not_blocked_when_not_duplicate():
    result = _eval(is_duplicate=False)
    assert result.decision == Decision.AUTO_APPROVED


def test_duplicate_checked_before_invoice_age():
    """Duplicate is checked before invoice age."""
    old_date = date.today() - timedelta(days=200)
    result = _eval(is_duplicate=True, invoice_date=old_date, max_invoice_age_days=180)
    assert result.rule_triggered == "duplicate_invoice"


# ─── Invoice age ───────────────────────────────────────────────────────────

def test_blocked_when_invoice_too_old():
    old_date = date.today() - timedelta(days=200)
    result = _eval(invoice_date=old_date, max_invoice_age_days=180)
    assert result.decision == Decision.BLOCKED
    assert result.rule_triggered == "invoice_age"


def test_not_blocked_when_invoice_within_age_limit():
    recent_date = date.today() - timedelta(days=30)
    result = _eval(invoice_date=recent_date, max_invoice_age_days=180)
    assert result.decision == Decision.AUTO_APPROVED


def test_invoice_age_not_checked_when_date_is_none():
    result = _eval(invoice_date=None, max_invoice_age_days=30)
    assert result.decision == Decision.AUTO_APPROVED


def test_invoice_age_not_checked_when_max_age_is_none():
    old_date = date.today() - timedelta(days=365)
    result = _eval(invoice_date=old_date, max_invoice_age_days=None)
    assert result.decision == Decision.AUTO_APPROVED


# ─── Tiered approval ──────────────────────────────────────────────────────

def test_tier_2_approval_above_limit():
    result = _eval(amount_minor=1_500_000, approval_tier_2_minor=1_000_000, block_threshold_minor=5_000_000)
    assert result.decision == Decision.APPROVAL_REQUIRED
    assert result.rule_triggered == "approval_tier_2"


def test_tier_1_approval_above_limit():
    result = _eval(amount_minor=150_000, approval_tier_1_minor=100_000)
    assert result.decision == Decision.APPROVAL_REQUIRED
    assert result.rule_triggered == "approval_tier_1"


def test_tier_2_takes_precedence_over_tier_1():
    result = _eval(
        amount_minor=2_000_000,
        approval_tier_1_minor=100_000,
        approval_tier_2_minor=1_000_000,
        block_threshold_minor=5_000_000,
    )
    assert result.rule_triggered == "approval_tier_2"


def test_tiered_approval_not_applied_when_none():
    """Without tier thresholds, falls through to base policy."""
    result = _eval(amount_minor=10_000, approval_tier_1_minor=None, approval_tier_2_minor=None)
    assert result.decision == Decision.AUTO_APPROVED


# ─── Base rules still enforced ────────────────────────────────────────────

def test_currency_blocked_through_invoice_policy():
    result = _eval(currency="JPY")
    assert result.decision == Decision.BLOCKED
    assert result.rule_triggered == "currency_allowlist"


def test_amount_block_through_invoice_policy():
    result = _eval(amount_minor=2_000_000)
    assert result.decision == Decision.BLOCKED
    assert result.rule_triggered == "amount_block_threshold"


def test_amount_approve_through_invoice_policy():
    result = _eval(amount_minor=60_000)
    assert result.decision == Decision.APPROVAL_REQUIRED
    assert result.rule_triggered == "amount_approve_threshold"


def test_unverified_supplier_through_invoice_policy():
    result = _eval(vendor="Unknown Vendor")
    assert result.decision == Decision.APPROVAL_REQUIRED
    assert result.rule_triggered == "verified_supplier"


def test_all_rules_pass_auto_approved():
    result = _eval()
    assert result.decision == Decision.AUTO_APPROVED
    assert result.rule_triggered == "none"


# ─── Rule priority: OCR → duplicate → age → base → tiers ─────────────────

def test_ocr_blocks_before_bad_currency():
    result = _eval(ocr_confidence=0.50, currency="JPY")
    assert result.rule_triggered == "ocr_confidence"


def test_base_blocked_before_tiered_approval():
    """A blocked base decision is never overridden by tiered approval."""
    result = _eval(amount_minor=2_000_000, approval_tier_1_minor=100_000)
    assert result.rule_triggered == "amount_block_threshold"
    assert result.decision == Decision.BLOCKED
