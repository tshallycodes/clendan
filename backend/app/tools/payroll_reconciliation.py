"""
Payroll Reconciliation Tool — detects ghost employees, missing payroll entries,
and salary discrepancies by comparing bank transactions against an employee roster.
Sub-agent tool, dispatched directly to its arq job.
Follows mandatory execution flow: receive → classify → execute → policy check → output → audit.
"""
import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import anthropic
from prisma import Json

from app.core.config import get_settings
from app.core.db import get_db
from app.core.execution import complete_execution
from app.core.logging import get_logger, get_trace_id
from app.queue.pool import push_to_dlq

logger = get_logger(__name__)

DEFAULT_PAYROLL_KEYWORDS = ["payroll", "salary", "wages", "payroll processing", "adp", "paychex"]
DISCREPANCY_THRESHOLD = 0.05  # 5%
MISSING_BLOCK_THRESHOLD = 0.30  # 30% missing → blocked


@dataclass
class RosterEntry:
    name: str
    expected_minor: int


@dataclass
class MatchedTransaction:
    transaction_id: str
    description: str
    amount_minor: int
    date: str
    extracted_name: str


@dataclass
class GhostEntry:
    transaction_id: str
    description: str
    amount_minor: int
    date: str
    extracted_name: str


@dataclass
class DiscrepancyEntry:
    name: str
    expected_minor: int
    actual_minor: int
    diff_pct: float
    transaction_id: str


@dataclass
class PayrollRunResult:
    run_id: str
    status: str
    matched: list[MatchedTransaction] = field(default_factory=list)
    ghosts: list[GhostEntry] = field(default_factory=list)
    missing: list[RosterEntry] = field(default_factory=list)
    discrepancies: list[DiscrepancyEntry] = field(default_factory=list)
    total_payroll_minor: int = 0


def _period_date_range(period: str) -> tuple[datetime, datetime]:
    """Convert '2025-01' to start/end datetimes covering the full month."""
    year, month = int(period[:4]), int(period[5:7])
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    return start, end


def _is_payroll_transaction(
    description: str | None,
    merchant_name: str | None,
    keywords: list[str] | None = None,
) -> bool:
    text = " ".join(filter(None, [description, merchant_name])).lower()
    kws = keywords if keywords else DEFAULT_PAYROLL_KEYWORDS
    return any(kw in text for kw in kws)


def _fuzzy_match(extracted: str, roster_name: str) -> bool:
    """Simple case-insensitive substring match for name matching."""
    a = extracted.lower().strip()
    b = roster_name.lower().strip()
    return a == b or a in b or b in a


class PayrollReconciliationTool:
    """
    Compares payroll bank transactions against an employee roster.
    Detects ghost employees, missing employees, and salary discrepancies.
    """

    async def run(
        self,
        period: str,
        tenant_id: str,
        tool_id: str,
        roster: list[dict[str, Any]],
        keywords: list[str] | None = None,
        discrepancy_threshold: float = DISCREPANCY_THRESHOLD,
        payroll_run_id: str | None = None,
        execution_id: str | None = None,
    ) -> dict[str, Any]:
        start = time.monotonic()
        trace_id = get_trace_id()
        db = get_db()

        # STEP 1: Receive + validate
        if not period or len(period) != 7 or period[4] != "-":
            raise ValueError("period must be in 'YYYY-MM' format")
        if not tenant_id:
            raise ValueError("tenant_id required")
        if not tool_id:
            raise ValueError("tool_id required")
        if not isinstance(roster, list):
            raise ValueError("roster must be a list of employee dicts")

        roster_entries: list[RosterEntry] = [
            RosterEntry(
                name=str(r.get("name", "")).strip(),
                expected_minor=int(r.get("expected_minor", 0)),
            )
            for r in roster
            if r.get("name")
        ]

        period_start, period_end = _period_date_range(period)

        # STEP 2: Classify — fetch payroll transactions scoped to tenant
        all_txns = await db.banktransaction.find_many(
            where={
                "tenant_id": tenant_id,
                "date": {"gte": period_start, "lt": period_end},
            }
        )

        payroll_txns = [
            t for t in all_txns
            if _is_payroll_transaction(t.description, t.merchant_name, keywords)
        ]

        if not payroll_txns:
            logger.info(
                "payroll_rec_no_transactions",
                extra={"tenant_id": tenant_id, "period": period},
            )

        # STEP 3: Execute — extract employee names from transaction descriptions via Claude
        extracted: list[dict[str, Any]] = []
        if payroll_txns:
            extracted = await self._extract_names_from_transactions(payroll_txns)

        # STEP 4: Cross-reference extracted names against roster
        matched: list[MatchedTransaction] = []
        ghosts: list[GhostEntry] = []
        discrepancies: list[DiscrepancyEntry] = []
        matched_roster_names: set[str] = set()

        for item in extracted:
            txn_id = item.get("transaction_id", "")
            extracted_name = item.get("name", "").strip()
            txn = next((t for t in payroll_txns if t.id == txn_id), None)
            if txn is None:
                continue

            roster_match = next(
                (r for r in roster_entries if _fuzzy_match(extracted_name, r.name)),
                None,
            )

            if roster_match is None:
                ghosts.append(GhostEntry(
                    transaction_id=txn.id,
                    description=txn.description or "",
                    amount_minor=txn.amount_minor,
                    date=txn.date.isoformat() if txn.date else "",
                    extracted_name=extracted_name,
                ))
            else:
                matched_roster_names.add(roster_match.name)
                diff = abs(txn.amount_minor - roster_match.expected_minor)
                diff_pct = diff / roster_match.expected_minor if roster_match.expected_minor > 0 else 0.0
                if diff_pct > discrepancy_threshold:
                    discrepancies.append(DiscrepancyEntry(
                        name=roster_match.name,
                        expected_minor=roster_match.expected_minor,
                        actual_minor=txn.amount_minor,
                        diff_pct=round(diff_pct * 100, 2),
                        transaction_id=txn.id,
                    ))
                else:
                    matched.append(MatchedTransaction(
                        transaction_id=txn.id,
                        description=txn.description or "",
                        amount_minor=txn.amount_minor,
                        date=txn.date.isoformat() if txn.date else "",
                        extracted_name=extracted_name,
                    ))

        missing: list[RosterEntry] = [
            r for r in roster_entries if r.name not in matched_roster_names
        ]

        total_payroll_minor = sum(t.amount_minor for t in payroll_txns)

        # STEP 4b: Policy check — determine status
        missing_ratio = len(missing) / len(roster_entries) if roster_entries else 0.0
        if missing_ratio > MISSING_BLOCK_THRESHOLD:
            status = "blocked"
        elif ghosts or discrepancies:
            status = "flagged"
        else:
            status = "clean"

        duration_ms = int((time.monotonic() - start) * 1000)

        # STEP 5: Write PayrollRun record
        results_payload: dict[str, Any] = {
            "trace_id": trace_id,
            "matched": [
                {
                    "transaction_id": m.transaction_id,
                    "description": m.description,
                    "amount_minor": m.amount_minor,
                    "date": m.date,
                    "extracted_name": m.extracted_name,
                }
                for m in matched
            ],
            "ghosts": [
                {
                    "transaction_id": g.transaction_id,
                    "description": g.description,
                    "amount_minor": g.amount_minor,
                    "date": g.date,
                    "extracted_name": g.extracted_name,
                }
                for g in ghosts
            ],
            "missing": [
                {"name": m.name, "expected_minor": m.expected_minor}
                for m in missing
            ],
            "discrepancies": [
                {
                    "name": d.name,
                    "expected_minor": d.expected_minor,
                    "actual_minor": d.actual_minor,
                    "diff_pct": d.diff_pct,
                    "transaction_id": d.transaction_id,
                }
                for d in discrepancies
            ],
        }

        results_json_wrapped = Json(results_payload)

        if payroll_run_id:
            run = await db.payrollrun.update(
                where={"id": payroll_run_id},
                data={
                    "status": status,
                    "total_payroll_minor": total_payroll_minor,
                    "matched_count": len(matched),
                    "ghost_count": len(ghosts),
                    "missing_count": len(missing),
                    "discrepancy_count": len(discrepancies),
                    "results_json": results_json_wrapped,
                },
            )
        else:
            run = await db.payrollrun.create(
                data={
                    "tenant_id": tenant_id,
                    "period": period,
                    "status": status,
                    "total_payroll_minor": total_payroll_minor,
                    "matched_count": len(matched),
                    "ghost_count": len(ghosts),
                    "missing_count": len(missing),
                    "discrepancy_count": len(discrepancies),
                    "results_json": results_json_wrapped,
                    "roster_json": Json([
                        {"name": r.name, "expected_minor": r.expected_minor}
                        for r in roster_entries
                    ]),
                }
            )

        # STEP 6: Write Execution record
        confidence = 1.0 if status == "clean" else 0.6 if status == "flagged" else 0.0

        if execution_id:
            await complete_execution(
                db=db, execution_id=execution_id, tool_id=tool_id,
                tenant_id=tenant_id, decision=status,
                confidence=confidence, duration_ms=duration_ms,
            )
            resolved_execution_id = execution_id
        else:
            execution = await db.execution.create(
                data={
                    "tenant_id": tenant_id,
                    "tool_id": tool_id,
                    "decision": status,
                    "confidence": confidence,
                    "status": "completed",
                    "duration_ms": duration_ms,
                    "input_ref": f"payroll-run:{run.id}:{trace_id[:8]}",
                }
            )
            resolved_execution_id = execution.id
            await db.payrollrun.update(
                where={"id": run.id},
                data={"execution_id": resolved_execution_id},
            )

        # STEP 7: Audit — append-only, must succeed or operation fails
        await db.auditlog.create(
            data={
                "tenant_id": tenant_id,
                "execution_id": resolved_execution_id,
                "actor": f"tool:{tool_id}",
                "action": "payroll_reconciliation:run",
                "reasoning_trace_json": Json({
                    "trace_id": trace_id,
                    "period": period,
                    "status": status,
                    "roster_size": len(roster_entries),
                    "matched_count": len(matched),
                    "ghost_count": len(ghosts),
                    "missing_count": len(missing),
                    "discrepancy_count": len(discrepancies),
                    "total_payroll_minor": total_payroll_minor,
                    "duration_ms": duration_ms,
                    "missing": [{"name": m.name, "expected_minor": m.expected_minor} for m in missing],
                    "ghosts": [{"name": g.extracted_name, "amount_minor": g.amount_minor} for g in ghosts],
                    "discrepancies": [
                        {
                            "name": d.name,
                            "expected_minor": d.expected_minor,
                            "actual_minor": d.actual_minor,
                            "diff_pct": d.diff_pct,
                        }
                        for d in discrepancies
                    ],
                }),
                "model_version": get_settings().claude_model,
            }
        )

        logger.info(
            "payroll_rec_complete",
            extra={
                "tenant_id": tenant_id,
                "period": period,
                "status": status,
                "matched": len(matched),
                "ghosts": len(ghosts),
                "missing": len(missing),
                "discrepancies": len(discrepancies),
                "duration_ms": duration_ms,
            },
        )

        return {
            "run_id": run.id,
            "status": status,
            "matched": len(matched),
            "ghosts": len(ghosts),
            "missing": len(missing),
            "discrepancies": len(discrepancies),
            "total_payroll_minor": total_payroll_minor,
        }

    async def _extract_names_from_transactions(
        self,
        transactions: list,
    ) -> list[dict[str, Any]]:
        """Use Claude to extract employee names from payroll transaction descriptions."""
        settings = get_settings()
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

        txn_list = [
            {
                "id": t.id,
                "description": t.description or "",
                "merchant_name": t.merchant_name or "",
                "amount_minor": t.amount_minor,
                "date": t.date.isoformat() if t.date else "",
            }
            for t in transactions
        ]

        prompt = f"""You are a payroll analyst. Extract the employee name from each payroll transaction.

TRANSACTIONS:
{json.dumps(txn_list, indent=2)}

For each transaction, return a JSON array with this exact shape:
[
  {{
    "transaction_id": "<id>",
    "name": "<employee full name, or empty string if no name found>"
  }}
]

Rules:
- Extract only actual person names from the description or merchant_name fields.
- If no employee name is identifiable, return an empty string for name.
- Return ONLY the JSON array — no markdown, no explanation."""

        last_exc: Exception = RuntimeError("No attempts made")
        for attempt in range(settings.max_agent_attempts):
            try:
                message = await client.messages.create(
                    model=settings.claude_model,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = message.content[0].text.strip()
                return json.loads(raw)
            except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
                last_exc = exc
                logger.warning(
                    "payroll_rec_transient_error",
                    extra={"attempt": attempt + 1, "error": str(exc)},
                )
                if attempt < settings.max_agent_attempts - 1:
                    await asyncio.sleep(settings.backoff_seconds * (attempt + 1))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "Claude returned non-JSON output for payroll name extraction"
                ) from exc
        raise RuntimeError(
            f"Claude API failed after {settings.max_agent_attempts} attempts: {last_exc}"
        ) from last_exc


async def run_payroll_rec_job(
    ctx: dict,
    payroll_run_id: str,
    tenant_id: str,
    tool_id: str,
    roster: list[dict[str, Any]],
    period: str,
) -> dict[str, Any]:
    """arq job wrapper for the Payroll Reconciliation Tool."""
    db = get_db()

    existing_run = await db.payrollrun.find_unique(where={"id": payroll_run_id})
    execution_id = existing_run.execution_id if existing_run else None

    tool_record = await db.tool.find_unique(where={"id": tool_id})
    cfg = (tool_record.config_json or {}) if tool_record else {}
    raw_keywords = cfg.get("payroll_keywords", "")
    keywords: list[str] | None = (
        [k.strip().lower() for k in raw_keywords.split(",") if k.strip()]
        if isinstance(raw_keywords, str) and raw_keywords.strip()
        else None
    )
    salary_tolerance_pct = float(cfg.get("payroll_salary_tolerance_pct", 5))
    discrepancy_threshold = salary_tolerance_pct / 100

    tool = PayrollReconciliationTool()
    try:
        result = await tool.run(
            period=period,
            tenant_id=tenant_id,
            tool_id=tool_id,
            roster=roster,
            keywords=keywords,
            discrepancy_threshold=discrepancy_threshold,
            payroll_run_id=payroll_run_id,
            execution_id=execution_id,
        )
        return result
    except Exception as exc:
        logger.error(
            "payroll_rec_job_failed",
            extra={"tenant_id": tenant_id, "payroll_run_id": payroll_run_id, "error": str(exc)},
        )
        job_try = ctx.get("job_try", 1)
        if job_try >= 3:
            await push_to_dlq(
                job_id=str(ctx.get("job_id", "unknown")),
                function_name="run_payroll_rec_job",
                error=str(exc),
            )
        raise
