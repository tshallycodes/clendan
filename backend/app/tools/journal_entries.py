"""
Journal Entry Tool — creates and posts payroll journal entries to the general ledger.
Sub-agent called by the Financial Orchestrator as a tool.
Follows mandatory execution flow: receive → classify → execute → policy check → output → audit.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.db import get_db
from app.core.logging import get_logger, get_trace_id

logger = get_logger(__name__)

APPROVAL_TTL_HOURS = 72


@dataclass
class EntryResult:
    entry_id: str
    status: str
    total_minor: int
    requires_approval: bool
    approval_id: str | None


class JournalEntryTool:
    """
    Creates and posts journal entries.
    Called by the Orchestrator as a tool — never invoked directly from routes.
    """

    async def create_payroll_entry(
        self,
        period: str,
        tenant_id: str,
        tool_id: str,
        lines: list[dict[str, Any]],
        description: str,
        auto_approve_threshold_minor: int = 5_000_000,
        entry_type: str = "payroll",
        currency: str = "GBP",
    ) -> EntryResult:
        """
        Create a journal entry for a given period.

        lines items must contain: account_code, account_name, debit_minor, credit_minor.
        Optional per-line: description.

        Raises ValueError if lines do not balance (sum debits != sum credits).
        """
        start = time.monotonic()
        trace_id = get_trace_id()
        db = get_db()

        # STEP 1: Receive + validate
        if not period:
            raise ValueError("period is required (format: YYYY-MM)")
        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not lines:
            raise ValueError("lines cannot be empty")

        total_debits = sum(int(ln.get("debit_minor", 0)) for ln in lines)
        total_credits = sum(int(ln.get("credit_minor", 0)) for ln in lines)
        if total_debits != total_credits:
            raise ValueError(
                f"Journal entry does not balance: debits={total_debits} credits={total_credits}"
            )

        total_minor = total_debits  # debit side == credit side

        # STEP 2: Classify — determine approval requirement
        requires_approval = total_minor > auto_approve_threshold_minor
        initial_status = "pending_approval" if requires_approval else "approved"

        # STEP 3: Execute — create entry and all lines atomically via nested create
        entry = await db.journalentry.create(
            data={
                "tenant_id": tenant_id,
                "period": period,
                "entry_type": entry_type,
                "description": description,
                "status": initial_status,
                "total_minor": total_minor,
                "currency": currency,
                "lines": {
                    "create": [
                        {
                            "account_code": str(ln["account_code"]),
                            "account_name": str(ln["account_name"]),
                            "debit_minor": int(ln.get("debit_minor", 0)),
                            "credit_minor": int(ln.get("credit_minor", 0)),
                            "description": ln.get("description"),
                        }
                        for ln in lines
                    ]
                },
            }
        )

        # STEP 4: Policy check — create Approval record if over threshold
        approval_id: str | None = None
        if requires_approval:
            # Approval model requires an execution_id — create a stub execution
            execution = await db.execution.create(
                data={
                    "tenant_id": tenant_id,
                    "tool_id": tool_id,
                    "input_ref": f"journal_entry:{entry.id}:{trace_id}",
                    "decision": "approval_required",
                    "confidence": 1.0,
                    "status": "pending",
                }
            )
            approval = await db.approval.create(
                data={
                    "tenant_id": tenant_id,
                    "execution_id": execution.id,
                    "status": "pending",
                    "expires_at": datetime.now(UTC) + timedelta(hours=APPROVAL_TTL_HOURS),
                }
            )
            approval_id = approval.id

        duration_ms = int((time.monotonic() - start) * 1000)

        # STEP 5: Audit — append-only, must succeed or operation fails
        await db.auditlog.create(
            data={
                "tenant_id": tenant_id,
                "actor": f"tool:{tool_id}",
                "action": "journal_entry:create",
                "reasoning_trace_json": {
                    "trace_id": trace_id,
                    "entry_id": entry.id,
                    "period": period,
                    "entry_type": entry_type,
                    "description": description,
                    "total_minor": total_minor,
                    "currency": currency,
                    "status": initial_status,
                    "requires_approval": requires_approval,
                    "approval_id": approval_id,
                    "line_count": len(lines),
                    "duration_ms": duration_ms,
                },
                "model_version": "journal_entries_v1",
            }
        )

        logger.info(
            "journal_entry_created",
            extra={
                "tenant_id": tenant_id,
                "entry_id": entry.id,
                "period": period,
                "entry_type": entry_type,
                "total_minor": total_minor,
                "status": initial_status,
                "duration_ms": duration_ms,
            },
        )

        return EntryResult(
            entry_id=entry.id,
            status=initial_status,
            total_minor=total_minor,
            requires_approval=requires_approval,
            approval_id=approval_id,
        )

    async def post_entry(self, entry_id: str, tenant_id: str) -> dict[str, Any]:
        """
        Post an approved journal entry (status: approved → posted).
        Raises ValueError if entry is not in approved status.
        """
        trace_id = get_trace_id()
        db = get_db()

        # Fetch and validate — always scope to tenant_id
        entry = await db.journalentry.find_first(
            where={"id": entry_id, "tenant_id": tenant_id}
        )
        if entry is None:
            raise ValueError(f"Journal entry {entry_id} not found for tenant")

        if entry.status != "approved":
            raise ValueError(
                f"Cannot post entry with status '{entry.status}' — must be 'approved'"
            )

        # Execute
        updated = await db.journalentry.update(
            where={"id": entry_id},
            data={"status": "posted", "posted_at": datetime.now(UTC)},
        )

        # Audit
        await db.auditlog.create(
            data={
                "tenant_id": tenant_id,
                "actor": f"tenant:{tenant_id}",
                "action": "journal_entry:post",
                "reasoning_trace_json": {
                    "trace_id": trace_id,
                    "entry_id": entry_id,
                    "period": entry.period,
                    "total_minor": entry.total_minor,
                    "posted_at": updated.posted_at.isoformat() if updated.posted_at else None,
                },
                "model_version": "journal_entries_v1",
            }
        )

        logger.info(
            "journal_entry_posted",
            extra={"tenant_id": tenant_id, "entry_id": entry_id},
        )

        return {
            "entry_id": updated.id,
            "status": updated.status,
            "posted_at": updated.posted_at.isoformat() if updated.posted_at else None,
        }


async def run_journal_entry_job(
    ctx: dict,
    entry_id: str,
    tenant_id: str,
    _tool_id: str,
) -> dict:
    """arq job wrapper for async journal entry post operations."""
    tool = JournalEntryTool()
    try:
        result = await tool.post_entry(entry_id=entry_id, tenant_id=tenant_id)
        return result
    except Exception as exc:
        logger.error(
            "journal_entry_job_failed",
            extra={"tenant_id": tenant_id, "entry_id": entry_id, "error": str(exc)},
        )
        from app.queue.pool import push_to_dlq
        job_try = ctx.get("job_try", 1)
        if job_try >= 3:
            await push_to_dlq(
                job_id=str(ctx.get("job_id", "unknown")),
                function_name="run_journal_entry_job",
                error=str(exc),
            )
        raise
