from dataclasses import dataclass
from datetime import date
from enum import Enum


class Decision(str, Enum):
    AUTO_APPROVED = "auto_approved"
    APPROVAL_REQUIRED = "approval_required"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class PolicyResult:
    decision: Decision
    reason: str
    rule_triggered: str


def evaluate_policy(
    *,
    amount_minor: int,
    currency: str,
    vendor: str,
    verified_suppliers: list[str],
    allowed_currencies: list[str],
    auto_threshold_minor: int,
    block_threshold_minor: int,
) -> PolicyResult:
    """
    Evaluate base policy rules in deterministic priority order.

    Rules: currency → amount_block → amount_approve → supplier → auto_approve
    Pure function — no side effects, no I/O.
    """
    if currency not in allowed_currencies:
        return PolicyResult(
            decision=Decision.BLOCKED,
            reason=f"Currency '{currency}' is not in the allowed list",
            rule_triggered="currency_allowlist",
        )

    if amount_minor > block_threshold_minor:
        return PolicyResult(
            decision=Decision.BLOCKED,
            reason=f"Amount {amount_minor} exceeds block threshold {block_threshold_minor}",
            rule_triggered="amount_block_threshold",
        )

    if amount_minor > auto_threshold_minor:
        return PolicyResult(
            decision=Decision.APPROVAL_REQUIRED,
            reason=f"Amount {amount_minor} exceeds auto-approve threshold {auto_threshold_minor}",
            rule_triggered="amount_approve_threshold",
        )

    if vendor not in verified_suppliers:
        return PolicyResult(
            decision=Decision.APPROVAL_REQUIRED,
            reason=f"Vendor '{vendor}' is not in the verified supplier list",
            rule_triggered="verified_supplier",
        )

    return PolicyResult(
        decision=Decision.AUTO_APPROVED,
        reason="All policy checks passed",
        rule_triggered="none",
    )


def evaluate_invoice_policy(
    *,
    # Base policy params
    amount_minor: int,
    currency: str,
    vendor: str,
    verified_suppliers: list[str],
    allowed_currencies: list[str],
    auto_threshold_minor: int,
    block_threshold_minor: int,
    # Invoice-specific params
    ocr_confidence: float,
    min_ocr_confidence: float = 0.85,
    is_duplicate: bool = False,
    invoice_date: date | None = None,
    max_invoice_age_days: int | None = None,
    approval_tier_1_minor: int | None = None,
    approval_tier_2_minor: int | None = None,
) -> PolicyResult:
    """
    Invoice-specific policy evaluation. Extends evaluate_policy with:
      ocr_confidence → duplicate → invoice_age → base_rules → tiered_approval

    Duplicate detection must be resolved by the caller (requires DB access).
    Pure function — no side effects, no I/O.
    """
    if ocr_confidence < min_ocr_confidence:
        return PolicyResult(
            decision=Decision.BLOCKED,
            reason=f"OCR confidence {ocr_confidence:.2f} is below minimum {min_ocr_confidence:.2f} — extraction unreliable",
            rule_triggered="ocr_confidence",
        )

    if is_duplicate:
        return PolicyResult(
            decision=Decision.BLOCKED,
            reason="Duplicate invoice number — already processed within the duplicate window",
            rule_triggered="duplicate_invoice",
        )

    if invoice_date is not None and max_invoice_age_days is not None:
        age_days = (date.today() - invoice_date).days
        if age_days > max_invoice_age_days:
            return PolicyResult(
                decision=Decision.BLOCKED,
                reason=f"Invoice is {age_days} days old, exceeds maximum of {max_invoice_age_days} days",
                rule_triggered="invoice_age",
            )

    base = evaluate_policy(
        amount_minor=amount_minor,
        currency=currency,
        vendor=vendor,
        verified_suppliers=verified_suppliers,
        allowed_currencies=allowed_currencies,
        auto_threshold_minor=auto_threshold_minor,
        block_threshold_minor=block_threshold_minor,
    )

    if base.decision == Decision.BLOCKED:
        return base

    # Tiered approval adds specificity to APPROVAL_REQUIRED decisions
    if approval_tier_2_minor is not None and amount_minor > approval_tier_2_minor:
        return PolicyResult(
            decision=Decision.APPROVAL_REQUIRED,
            reason=f"Amount {amount_minor} exceeds tier-2 approval limit {approval_tier_2_minor} — senior sign-off required",
            rule_triggered="approval_tier_2",
        )

    if approval_tier_1_minor is not None and amount_minor > approval_tier_1_minor:
        return PolicyResult(
            decision=Decision.APPROVAL_REQUIRED,
            reason=f"Amount {amount_minor} exceeds tier-1 approval limit {approval_tier_1_minor}",
            rule_triggered="approval_tier_1",
        )

    return base
