from dataclasses import dataclass
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
    Evaluate all policy rules in deterministic priority order.

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
