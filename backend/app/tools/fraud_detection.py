"""
Fraud Detection Tool — sub-agent tool. Called by Financial Orchestrator as a tool.
Scores a batch of transactions for fraud risk and decides allow / flag / block per transaction,
then derives an overall execution decision.
"""
from __future__ import annotations

import asyncio
import json
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
from app.tools.base import BaseTool, ToolOutput, ToolType

logger = get_logger(__name__)

_ACTOR = "tool:fraud_detection:v1"
_MODEL_VERSION = "fraud_detection-v1"
_ACTION_RANK: dict[str, int] = {"allow": 0, "flag": 1, "block": 2}


# ---------------------------------------------------------------------------
# Internal data models
# ---------------------------------------------------------------------------


class _ToolPolicy(BaseModel):
    risk_score_block: float = 0.85
    velocity_max_txns: int = 10
    velocity_window_minutes: int = 60
    review_score_threshold: float = 0.65
    velocity_max_amount: int = 500000            # minor units ($5,000)
    single_transaction_max: int = 1000000        # minor units ($10,000)
    new_merchant_risk_boost: float = 0.15
    geo_velocity_max_kmph: int = 800
    unusual_hours_start: int = 0
    unusual_hours_end: int = 5
    unusual_hours_risk_boost: float = 0.10
    card_not_present_risk_boost: float = 0.12
    round_amount_risk_boost: float = 0.08
    ip_reputation_check_enabled: bool = True
    device_fingerprint_enabled: bool = True
    model_retrain_frequency_days: int = 14
    sca_required_above: int = 3000               # minor units (~€30)


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
    ai_category: str | None
    status: str


class _ClaudeTransactionResult(BaseModel):
    transaction_id: str
    risk_score: float
    signals: list[str]
    action: Literal["allow", "flag", "block"]
    reasoning: str


class _TransactionDecision(BaseModel):
    transaction_id: str
    account_id: str
    risk_score: float
    signals: list[str]
    action: Literal["allow", "flag", "block"]
    reasoning: str


# ---------------------------------------------------------------------------
# Policy helper
# ---------------------------------------------------------------------------


def _parse_policy(config_json: dict) -> _ToolPolicy:
    raw = config_json.get("policy", config_json)
    return _ToolPolicy(
        risk_score_block=raw.get("risk_score_block", 0.85),
        velocity_max_txns=raw.get("velocity_max_txns", 10),
        velocity_window_minutes=raw.get("velocity_window_minutes", 60),
        review_score_threshold=raw.get("review_score_threshold", 0.65),
        velocity_max_amount=raw.get("velocity_max_amount", 500000),
        single_transaction_max=raw.get("single_transaction_max", 1000000),
        new_merchant_risk_boost=raw.get("new_merchant_risk_boost", 0.15),
        geo_velocity_max_kmph=raw.get("geo_velocity_max_kmph", 800),
        unusual_hours_start=raw.get("unusual_hours_start", 0),
        unusual_hours_end=raw.get("unusual_hours_end", 5),
        unusual_hours_risk_boost=raw.get("unusual_hours_risk_boost", 0.10),
        card_not_present_risk_boost=raw.get("card_not_present_risk_boost", 0.12),
        round_amount_risk_boost=raw.get("round_amount_risk_boost", 0.08),
        ip_reputation_check_enabled=raw.get("ip_reputation_check_enabled", True),
        device_fingerprint_enabled=raw.get("device_fingerprint_enabled", True),
        model_retrain_frequency_days=raw.get("model_retrain_frequency_days", 14),
        sca_required_above=raw.get("sca_required_above", 3000),
    )


# ---------------------------------------------------------------------------
# Velocity check
# ---------------------------------------------------------------------------


async def _check_velocity(
    account_id: str,
    tenant_id: str,
    window_minutes: int,
    max_txns: int,
) -> bool:
    """Return True if transaction count for account exceeds velocity limit."""
    db = get_db()
    cutoff = datetime.now(UTC) - timedelta(minutes=window_minutes)
    result = await db.banktransaction.count(
        where={
            "tenant_id": tenant_id,
            "account_id": account_id,
            "date": {"gte": cutoff},
        }
    )
    return result > max_txns


# ---------------------------------------------------------------------------
# Claude scoring
# ---------------------------------------------------------------------------


def _build_claude_prompt(transactions: list[_TransactionRecord]) -> str:
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
                "ai_category": t.ai_category,
            }
            for t in transactions
        ],
        indent=2,
    )
    return (
        "You are a financial fraud detection model. Analyse each transaction below and return "
        "a JSON array — one object per transaction — with exactly these fields:\n"
        '  "transaction_id": string (copy from input),\n'
        '  "risk_score": float 0.0–1.0 (higher = more suspicious),\n'
        '  "signals": array of short signal strings e.g. ["duplicate_amount", "new_merchant"],\n'
        '  "action": one of "allow" | "flag" | "block",\n'
        '  "reasoning": one concise sentence.\n\n'
        "Rules:\n"
        "- risk_score >= 0.85 → action must be block\n"
        "- risk_score >= 0.5  → action must be at least flag\n"
        "- risk_score < 0.5   → action allow\n"
        "Return ONLY a valid JSON array. No markdown, no prose.\n\n"
        f"Transactions:\n{serialised}"
    )


async def _call_claude(
    transactions: list[_TransactionRecord],
    settings_obj,
) -> list[_ClaudeTransactionResult]:
    client = AsyncAnthropic(api_key=settings_obj.anthropic_api_key)
    prompt = _build_claude_prompt(transactions)
    last_exc: Exception | None = None

    for attempt in range(settings_obj.max_agent_attempts):
        try:
            message = await client.messages.create(
                model=settings_obj.claude_model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = message.content[0].text.strip()
            parsed = json.loads(raw_text)
            if not isinstance(parsed, list):
                raise ValueError("Claude response is not a JSON array")
            return [_ClaudeTransactionResult(**item) for item in parsed]
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

    raise RuntimeError(f"Claude API failed after {settings_obj.max_agent_attempts} attempts: {last_exc}")


# ---------------------------------------------------------------------------
# Core execution
# ---------------------------------------------------------------------------


async def _execute_fraud_detection(
    tenant_id: str,
    tool_id: str,
    execution_id: str,
    transaction_ids: list[str],
) -> dict:
    settings_obj = get_settings()
    db = get_db()

    # Fetch tool config
    tool = await db.tool.find_first(
        where={"id": tool_id, "tenant_id": tenant_id}
    )
    if tool is None:
        raise ValueError(f"Tool {tool_id} not found for tenant {tenant_id}")

    config_raw: dict = tool.config_json if isinstance(tool.config_json, dict) else {}
    policy = _parse_policy(config_raw)

    # Fetch transactions scoped to tenant
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
            ai_category=t.ai_category,
            status=t.status,
        )
        for t in raw_txns
    ]

    # Claude scoring
    claude_results = await _call_claude(transactions, settings_obj)

    # Index results by transaction_id for fast lookup
    claude_map: dict[str, _ClaudeTransactionResult] = {r.transaction_id: r for r in claude_results}

    # Velocity checks and final per-transaction decisions
    decisions: list[_TransactionDecision] = []
    for txn in transactions:
        claude_result = claude_map.get(txn.id)
        if claude_result is None:
            # Claude did not return a result — treat as high risk
            decisions.append(
                _TransactionDecision(
                    transaction_id=txn.id,
                    account_id=txn.account_id,
                    risk_score=1.0,
                    signals=["missing_claude_score"],
                    action="block",
                    reasoning="Claude did not return a score for this transaction.",
                )
            )
            continue

        signals = list(claude_result.signals)
        action: Literal["allow", "flag", "block"] = claude_result.action
        risk_score = claude_result.risk_score

        # Velocity check
        velocity_exceeded = await _check_velocity(
            account_id=txn.account_id,
            tenant_id=tenant_id,
            window_minutes=policy.velocity_window_minutes,
            max_txns=policy.velocity_max_txns,
        )
        if velocity_exceeded:
            signals.append("velocity_exceeded")
            if _ACTION_RANK[action] < _ACTION_RANK["flag"]:
                action = "flag"

        # Hard block threshold
        if risk_score >= policy.risk_score_block and action != "block":
            action = "block"

        decisions.append(
            _TransactionDecision(
                transaction_id=txn.id,
                account_id=txn.account_id,
                risk_score=risk_score,
                signals=signals,
                action=action,
                reasoning=claude_result.reasoning,
            )
        )

    # Derive overall decision
    has_block = any(d.action == "block" for d in decisions)
    has_flag = any(d.action == "flag" for d in decisions)

    if has_block:
        overall_decision = "blocked"
    elif has_flag:
        overall_decision = "approval_required"
    else:
        overall_decision = "auto_approved"

    avg_risk = sum(d.risk_score for d in decisions) / len(decisions)
    confidence = round(1.0 - avg_risk if overall_decision == "auto_approved" else avg_risk, 4)

    # Build reasoning trace
    reasoning_trace: dict = {
        "overall_decision": overall_decision,
        "transaction_count": len(decisions),
        "policy": policy.model_dump(),
        "per_transaction": [
            {
                "transaction_id": d.transaction_id,
                "account_id": d.account_id,
                "risk_score": d.risk_score,
                "signals": d.signals,
                "action": d.action,
                "reasoning": d.reasoning,
            }
            for d in decisions
        ],
    }

    # Audit log BEFORE updating anything — operation fails if audit fails
    await write_audit_log(
        tenant_id=tenant_id,
        actor=_ACTOR,
        action=f"fraud_detection:{overall_decision}",
        reasoning_trace=reasoning_trace,
        model_version=_MODEL_VERSION,
        execution_id=execution_id,
    )

    # Update transaction statuses in DB
    flag_ids = [d.transaction_id for d in decisions if d.action == "flag"]
    block_ids = [d.transaction_id for d in decisions if d.action == "block"]

    if flag_ids:
        await db.banktransaction.update_many(
            where={"id": {"in": flag_ids}, "tenant_id": tenant_id},
            data={"status": "flagged"},
        )
    if block_ids:
        await db.banktransaction.update_many(
            where={"id": {"in": block_ids}, "tenant_id": tenant_id},
            data={"status": "blocked"},
        )

    actions_taken: list[str] = []
    if flag_ids:
        actions_taken.append(f"flagged {len(flag_ids)} transaction(s)")
    if block_ids:
        actions_taken.append(f"blocked {len(block_ids)} transaction(s)")
    if not flag_ids and not block_ids:
        actions_taken.append("all transactions allowed — no status change")

    return {
        "decision": overall_decision,
        "confidence": confidence,
        "reasoning": json.dumps(reasoning_trace),
        "actions_taken": actions_taken,
        "output_data": reasoning_trace,
    }


# ---------------------------------------------------------------------------
# arq job entrypoint
# ---------------------------------------------------------------------------


async def run_fraud_detection_job(
    ctx: dict,
    *,
    execution_id: str,
    tenant_id: str,
    tool_id: str,
    transaction_ids: list[str],
) -> dict:
    db = get_db()
    settings_obj = get_settings()
    start_ms = int(time.time() * 1000)

    try:
        result = await _execute_fraud_detection(
            tenant_id, tool_id, execution_id, transaction_ids
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
                function_name="run_fraud_detection_job",
                error=str(exc),
            )
        raise


# ---------------------------------------------------------------------------
# BaseTool class (orchestrator interface)
# ---------------------------------------------------------------------------


class FraudDetectionTool(BaseTool):
    TOOL_TYPE = ToolType.FRAUD_DETECTION
    VERSION = 1

    async def execute(self, input_data: dict, tenant_id: str) -> ToolOutput:
        execution_id: str = input_data["execution_id"]
        tool_id: str = input_data["tool_id"]
        transaction_ids: list[str] = input_data["transaction_ids"]

        result = await _execute_fraud_detection(
            tenant_id, tool_id, execution_id, transaction_ids
        )
        return ToolOutput(
            tool_type=self.TOOL_TYPE,
            decision=result["decision"],
            confidence=result["confidence"],
            reasoning=result["reasoning"],
            actions_taken=result["actions_taken"],
            output_data=result["output_data"],
        )
