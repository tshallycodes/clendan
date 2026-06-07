"""
Compliance Worker — sub-agent worker. Called by Financial Orchestrator as a tool.
Checks a batch of transactions against active compliance frameworks (AML, KYC, GDPR),
generates a structured compliance report, and derives an execution decision.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import UTC, datetime, timedelta
from typing import Literal

from anthropic import APIConnectionError, APIStatusError, AsyncAnthropic
from pydantic import BaseModel
from app.audit.logger import write_audit_log
from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.queue.pool import push_to_dlq
from app.workers.base import BaseWorker, WorkerOutput, WorkerType
from app.workers.compliance_policy import _WorkerConfig, _parse_config

logger = get_logger(__name__)

_ACTOR = "worker:compliance:v1"
_MODEL_VERSION = "compliance-v1"

_PII_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"  # email
    r"|\b[A-Z][a-z]+\s[A-Z][a-z]+\b",  # name-like: two capitalised words
)


# ---------------------------------------------------------------------------
# Internal data models
# ---------------------------------------------------------------------------


class _TransactionRecord(BaseModel):
    id: str
    tenant_id: str
    account_id: str
    amount_minor: int
    currency: str
    merchant_name: str | None
    description: str | None
    date: datetime
    category: str | None
    status: str


class _Violation(BaseModel):
    transaction_id: str
    framework: str
    severity: Literal["high", "medium", "low"]
    rule_triggered: str
    description: str
    required_action: str


class _ClaudeResponse(BaseModel):
    violations: list[_Violation]
    overall_status: Literal["compliant", "violations_found"]
    summary: str
    confidence: float


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def _active_frameworks(config: _WorkerConfig, requested: list[str]) -> list[str]:
    """Intersect requested frameworks with those enabled in worker config."""
    enabled = {f.strip().upper() for f in config.frameworks.split(",")}
    return [f.upper() for f in requested if f.upper() in enabled]


# ---------------------------------------------------------------------------
# Hard-rule violation detectors (deterministic, no LLM)
# ---------------------------------------------------------------------------


def _detect_hard_rule_violations(
    transactions: list[_TransactionRecord],
    frameworks: list[str],
    report_above_minor: int,
) -> list[_Violation]:
    violations: list[_Violation] = []

    for txn in transactions:
        if "AML" in frameworks and txn.amount_minor >= report_above_minor:
            amount_display = txn.amount_minor // 100
            threshold_display = report_above_minor // 100
            violations.append(
                _Violation(
                    transaction_id=txn.id,
                    framework="AML",
                    severity="high",
                    rule_triggered="transaction_above_reporting_threshold",
                    description=(
                        f"Transaction of {txn.currency} {amount_display} "
                        f"exceeds AML reporting threshold of {txn.currency} {threshold_display}"
                    ),
                    required_action="File SAR report",
                )
            )

        if "KYC" in frameworks and (not txn.merchant_name or txn.merchant_name.strip() == ""):
            violations.append(
                _Violation(
                    transaction_id=txn.id,
                    framework="KYC",
                    severity="medium",
                    rule_triggered="unknown_counterparty",
                    description="Transaction has no merchant name — counterparty identity is unverified",
                    required_action="Obtain counterparty identification before proceeding",
                )
            )

        if "GDPR" in frameworks and txn.description and _PII_PATTERN.search(txn.description):
            violations.append(
                _Violation(
                    transaction_id=txn.id,
                    framework="GDPR",
                    severity="medium",
                    rule_triggered="pii_in_transaction_description",
                    description="Transaction description appears to contain personal data (name or email)",
                    required_action="Redact PII from transaction description and review data handling",
                )
            )

    return violations


def _detect_structuring(
    transactions: list[_TransactionRecord],
    report_above_minor: int,
) -> list[_Violation]:
    """Flag potential structuring: multiple sub-threshold transactions summing near the threshold."""
    low_bound = int(report_above_minor * 0.7)
    near_threshold = [
        t for t in transactions
        if low_bound <= t.amount_minor < report_above_minor
    ]
    if len(near_threshold) < 2:
        return []
    total = sum(t.amount_minor for t in near_threshold)
    if total < report_above_minor:
        return []
    return [
        _Violation(
            transaction_id=t.id,
            framework="AML",
            severity="high",
            rule_triggered="potential_structuring",
            description=(
                f"Multiple transactions below AML threshold that collectively "
                f"sum to {total // 100} — potential structuring pattern"
            ),
            required_action="Investigate for structuring / smurfing and file SAR if confirmed",
        )
        for t in near_threshold
    ]


# ---------------------------------------------------------------------------
# Claude prompt and call
# ---------------------------------------------------------------------------


def _build_claude_prompt(
    transactions: list[_TransactionRecord],
    frameworks: list[str],
) -> str:
    serialised = json.dumps(
        [
            {
                "transaction_id": t.id,
                "account_id": t.account_id,
                "amount_minor": t.amount_minor,
                "currency": t.currency,
                "merchant_name": t.merchant_name,
                "description": t.description,
                "date": t.date.isoformat(),
                "category": t.category,
            }
            for t in transactions
        ],
        indent=2,
    )
    frameworks_str = ", ".join(frameworks)
    return (
        f"You are a financial compliance analyst. Check each transaction below against the "
        f"following active frameworks: {frameworks_str}.\n\n"
        "Return a JSON object with exactly these fields:\n"
        '  "violations": array of violation objects (may be empty),\n'
        '  "overall_status": "compliant" | "violations_found",\n'
        '  "summary": one concise paragraph summarising findings,\n'
        '  "confidence": float 0.0–1.0 (your confidence in this assessment).\n\n'
        "Each violation object must have:\n"
        '  "transaction_id": string,\n'
        '  "framework": "AML" | "KYC" | "GDPR",\n'
        '  "severity": "high" | "medium" | "low",\n'
        '  "rule_triggered": short snake_case rule name,\n'
        '  "description": human-readable explanation,\n'
        '  "required_action": what must be done.\n\n'
        "AML rules: flag unusual payment patterns, potential layering, "
        "transactions to high-risk jurisdictions.\n"
        "KYC rules: flag missing or suspiciously generic counterparty names, "
        "transactions with no verifiable identity.\n"
        "GDPR rules: flag descriptions containing personal data such as names, "
        "email addresses, or national ID numbers.\n\n"
        "Return ONLY a valid JSON object. No markdown, no prose.\n\n"
        f"Transactions:\n{serialised}"
    )


async def _call_claude(
    transactions: list[_TransactionRecord],
    frameworks: list[str],
    settings_obj,
) -> _ClaudeResponse:
    client = AsyncAnthropic(api_key=settings_obj.anthropic_api_key)
    prompt = _build_claude_prompt(transactions, frameworks)
    last_exc: Exception | None = None

    for attempt in range(settings_obj.max_agent_attempts):
        try:
            message = await client.messages.create(
                model=settings_obj.claude_model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = message.content[0].text.strip()
            parsed = json.loads(raw_text)
            if not isinstance(parsed, dict):
                raise ValueError("Claude response is not a JSON object")
            violations = [_Violation(**v) for v in parsed.get("violations", [])]
            return _ClaudeResponse(
                violations=violations,
                overall_status=parsed.get("overall_status", "compliant"),
                summary=parsed.get("summary", ""),
                confidence=float(parsed.get("confidence", 0.0)),
            )
        except (APIStatusError, APIConnectionError) as exc:
            last_exc = exc
            logger.error(
                "claude_api_error",
                extra={"attempt": attempt + 1, "error": str(exc)},
            )
            if attempt < settings_obj.max_agent_attempts - 1:
                await asyncio.sleep(settings_obj.backoff_seconds * (attempt + 1))
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            raise RuntimeError(f"Claude returned unparseable response: {exc}") from exc

    raise RuntimeError(
        f"Claude API failed after {settings_obj.max_agent_attempts} attempts: {last_exc}"
    )


# ---------------------------------------------------------------------------
# Decision logic
# ---------------------------------------------------------------------------


def _derive_decision(violations: list[_Violation]) -> str:
    if any(v.severity == "high" for v in violations):
        return "blocked"
    if any(v.severity == "medium" for v in violations):
        return "approval_required"
    return "auto_approved"


def _deduplicate_violations(violations: list[_Violation]) -> list[_Violation]:
    """Remove duplicates by (transaction_id, rule_triggered), preserving order."""
    seen: set[tuple[str, str]] = set()
    result: list[_Violation] = []
    for v in violations:
        key = (v.transaction_id, v.rule_triggered)
        if key not in seen:
            seen.add(key)
            result.append(v)
    return result


# ---------------------------------------------------------------------------
# Core execution
# ---------------------------------------------------------------------------


async def _execute_compliance(
    tenant_id: str,
    worker_id: str,
    execution_id: str,
    transaction_ids: list[str],
    frameworks: list[str],
) -> dict:
    settings_obj = get_settings()
    db = get_db()

    worker = await db.worker.find_first(
        where={"id": worker_id, "tenant_id": tenant_id}
    )
    if worker is None:
        raise ValueError(f"Worker {worker_id} not found for tenant {tenant_id}")

    config_raw: dict = worker.config_json if isinstance(worker.config_json, dict) else {}
    config = _parse_config(config_raw)
    active = _active_frameworks(config, frameworks)

    if not active:
        raise ValueError(
            f"No active frameworks match the requested set {frameworks}. "
            f"Worker config enables: {config.frameworks}"
        )

    raw_txns = await db.banktransaction.find_many(
        where={"id": {"in": transaction_ids}, "tenant_id": tenant_id}
    )
    if not raw_txns:
        raise ValueError("No transactions found for supplied IDs within this tenant")

    transactions = [
        _TransactionRecord(
            id=t.id,
            tenant_id=t.tenant_id,
            account_id=t.account_id,
            amount_minor=t.amount_minor,
            currency=t.currency,
            merchant_name=t.merchant_name,
            description=t.description,
            date=t.date,
            category=t.category,
            status=t.status,
        )
        for t in raw_txns
    ]

    hard_violations = _detect_hard_rule_violations(transactions, active, config.report_above_minor)
    if "AML" in active:
        hard_violations += _detect_structuring(transactions, config.report_above_minor)

    claude_response = await _call_claude(transactions, active, settings_obj)

    all_violations = _deduplicate_violations(hard_violations + claude_response.violations)
    decision = _derive_decision(all_violations)
    confidence = claude_response.confidence

    violation_ids = [v.transaction_id for v in all_violations]
    actions_taken = (
        [
            f"{v.framework} [{v.severity}] {v.transaction_id}: {v.required_action}"
            for v in all_violations
        ]
        or ["no violations detected — all transactions compliant"]
    )

    reasoning_trace: dict = {
        "transaction_count": len(transactions),
        "transaction_ids": [t.id for t in transactions],
        "frameworks_checked": active,
        "violations_count": len(all_violations),
        "violation_ids": violation_ids,
        "overall_status": claude_response.overall_status,
        "summary": claude_response.summary,
    }

    # Audit log BEFORE updating execution record — operation fails if audit fails
    await write_audit_log(
        tenant_id=tenant_id,
        actor=_ACTOR,
        action=f"compliance_check:{decision}",
        reasoning_trace=reasoning_trace,
        model_version=_MODEL_VERSION,
        execution_id=execution_id,
    )

    report: dict = {
        "violations": [v.model_dump() for v in all_violations],
        "overall_status": claude_response.overall_status,
        "summary": claude_response.summary,
        "frameworks_checked": active,
        "transaction_count": len(transactions),
    }

    return {
        "decision": decision,
        "confidence": confidence,
        "reasoning": json.dumps(reasoning_trace),
        "actions_taken": actions_taken,
        "output_data": report,
    }


# ---------------------------------------------------------------------------
# arq job entrypoint
# ---------------------------------------------------------------------------


async def run_compliance_job(
    ctx: dict,
    *,
    execution_id: str,
    tenant_id: str,
    worker_id: str,
    transaction_ids: list[str],
    frameworks: list[str],
) -> dict:
    db = get_db()
    settings_obj = get_settings()
    start_ms = int(time.time() * 1000)

    try:
        result = await _execute_compliance(
            tenant_id, worker_id, execution_id, transaction_ids, frameworks
        )
        duration_ms = int(time.time() * 1000) - start_ms
        await db.execution.update(
            where={"id": execution_id},
            data={
                "status": "completed",
                "decision": result["decision"],
                "confidence": result["confidence"],
                "duration_ms": duration_ms,
            },
        )
        if result["decision"] == "approval_required":
            await db.approval.create(
                data={
                    "tenant_id": tenant_id,
                    "execution_id": execution_id,
                    "expires_at": datetime.now(UTC)
                    + timedelta(seconds=settings_obj.approval_ttl_seconds),
                }
            )
        return result
    except Exception as exc:
        try:
            await db.execution.update(
                where={"id": execution_id},
                data={"status": "failed", "decision": "failed"},
            )
        except Exception:
            pass
        if ctx.get("job_try", 1) >= 3:
            await push_to_dlq(
                job_id=str(ctx.get("job_id", "unknown")),
                function_name="run_compliance_job",
                error=str(exc),
            )
        raise


# ---------------------------------------------------------------------------
# BaseWorker class (orchestrator interface)
# ---------------------------------------------------------------------------


class ComplianceWorker(BaseWorker):
    WORKER_TYPE = WorkerType.COMPLIANCE
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> WorkerOutput:
        execution_id: str = input_data["execution_id"]
        worker_id: str = input_data["worker_id"]
        transaction_ids: list[str] = input_data["transaction_ids"]
        frameworks: list[str] = input_data["frameworks"]

        result = await _execute_compliance(
            tenant_id, worker_id, execution_id, transaction_ids, frameworks
        )
        return WorkerOutput(
            worker_type=self.WORKER_TYPE,
            decision=result["decision"],
            confidence=result["confidence"],
            reasoning=result["reasoning"],
            actions_taken=result["actions_taken"],
            output_data=result["output_data"],
        )
