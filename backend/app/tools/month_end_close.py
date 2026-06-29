"""
Month-End Close Tool — evaluates checklist tasks required to close the books for a period.
Sub-agent called by the Financial Orchestrator as a tool.
Follows mandatory execution flow: receive → validate → execute → policy check → output → audit.
"""
from __future__ import annotations

import json
import time
from datetime import date, datetime, UTC
from typing import Any

from app.core.db import get_db
from app.core.logging import get_logger, get_trace_id
from app.queue.pool import push_to_dlq

logger = get_logger(__name__)

# Tasks that can be auto-evaluated from the DB
AUTO_TASKS = {"all_transactions_categorised", "reconciliation_complete", "approvals_resolved"}

TASK_LABELS: dict[str, str] = {
    "all_transactions_categorised": "All transactions categorised",
    "reconciliation_complete": "Reconciliation complete",
    "approvals_resolved": "All approvals resolved",
    "payroll_reconciled": "Payroll reconciled",
    "sign_offs_collected": "Sign-offs collected",
}


def _parse_period(period: str) -> tuple[datetime, datetime]:
    """Parse 'YYYY-MM' into (period_start, period_end) as UTC datetimes."""
    year, month = int(period[:4]), int(period[5:7])
    period_start = datetime(year, month, 1, tzinfo=UTC)
    if month == 12:
        period_end = datetime(year + 1, 1, 1, tzinfo=UTC)
    else:
        period_end = datetime(year, month + 1, 1, tzinfo=UTC)
    return period_start, period_end


def _build_default_tasks() -> list[dict[str, Any]]:
    return [
        {
            "task_key": key,
            "label": label,
            "status": "pending",
            "completed_at": None,
            "completed_by": None,
            "notes": None,
        }
        for key, label in TASK_LABELS.items()
    ]


def _merge_tasks(
    existing: list[dict[str, Any]],
    updates: dict[str, str],
) -> list[dict[str, Any]]:
    """Return existing tasks with auto-evaluated statuses applied, preserving manual data."""
    existing_map = {t["task_key"]: t for t in existing}
    result: list[dict[str, Any]] = []
    for key, label in TASK_LABELS.items():
        task = existing_map.get(key, {
            "task_key": key,
            "label": label,
            "status": "pending",
            "completed_at": None,
            "completed_by": None,
            "notes": None,
        })
        if key in updates:
            task = dict(task)
            new_status = updates[key]
            if new_status == "complete" and task["status"] != "complete":
                task["status"] = "complete"
                task["completed_at"] = datetime.now(UTC).isoformat()
            elif new_status in ("pending", "blocked"):
                task["status"] = new_status
        result.append(task)
    return result


class MonthEndCloseTool:
    """
    Evaluates auto-checkable month-end close tasks by querying the DB.
    Called by the Orchestrator as a tool — never invoked directly from routes.
    """

    async def run(
        self,
        period: str,
        tenant_id: str,
        tool_id: str,
    ) -> dict[str, Any]:
        start = time.monotonic()
        trace_id = get_trace_id()
        db = get_db()

        # STEP 1: Receive + validate
        if not period or len(period) != 7 or period[4] != "-":
            raise ValueError("period must be in YYYY-MM format")
        if not tenant_id:
            raise ValueError("tenant_id required")

        period_start, period_end = _parse_period(period)

        logger.info(
            "month_end_close_start",
            extra={"tenant_id": tenant_id, "period": period, "trace_id": trace_id},
        )

        # STEP 2: Fetch the existing close run
        close_run = await db.monthendcloserun.find_unique(
            where={"tenant_id_period": {"tenant_id": tenant_id, "period": period}}
        )
        if not close_run:
            raise ValueError(f"No close run found for period {period}")

        existing_tasks: list[dict[str, Any]] = (
            close_run.tasks_json if isinstance(close_run.tasks_json, list) else []
        )
        if not existing_tasks:
            existing_tasks = _build_default_tasks()

        # STEP 3: Execute — evaluate each auto-checkable task
        task_updates: dict[str, str] = {}

        # Task 1: all_transactions_categorised
        pending_txn_count = await db.banktransaction.count(
            where={
                "tenant_id": tenant_id,
                "date": {"gte": period_start, "lt": period_end},
                "status": {"in": ["pending", "unprocessed"]},
            }
        )
        task_updates["all_transactions_categorised"] = (
            "pending" if pending_txn_count > 0 else "complete"
        )

        # Task 2: reconciliation_complete
        completed_recon = await db.reconciliationrun.find_first(
            where={
                "tenant_id": tenant_id,
                "period_start": {"gte": period_start},
                "status": "completed",
            }
        )
        task_updates["reconciliation_complete"] = (
            "complete" if completed_recon else "pending"
        )

        # Task 3: approvals_resolved
        pending_approval_count = await db.approval.count(
            where={
                "tenant_id": tenant_id,
                "status": "pending",
            }
        )
        task_updates["approvals_resolved"] = (
            "blocked" if pending_approval_count > 0 else "complete"
        )

        # Tasks 4 & 5 (payroll_reconciled, sign_offs_collected) are manual — no auto-check

        # STEP 4: Policy check — merge updates into task list
        updated_tasks = _merge_tasks(existing_tasks, task_updates)

        # Determine overall close run status
        statuses = [t["status"] for t in updated_tasks]
        if all(s == "complete" for s in statuses):
            run_status = "closed"
        elif any(s == "complete" for s in statuses):
            run_status = "in_progress"
        else:
            run_status = "open"

        duration_ms = int((time.monotonic() - start) * 1000)

        # STEP 5: Output — write updated tasks and status to DB
        updated_run = await db.monthendcloserun.update(
            where={"id": close_run.id},
            data={
                "tasks_json": updated_tasks,
                "status": run_status,
                "closed_at": datetime.now(UTC) if run_status == "closed" else None,
            },
        )

        # STEP 6: Audit — append-only, must succeed or operation fails
        execution = await db.execution.create(
            data={
                "tenant_id": tenant_id,
                "tool_id": tool_id,
                "input_ref": json.dumps({"period": period, "trace_id": trace_id}),
                "decision": "auto",
                "confidence": 1.0,
                "status": "completed",
                "duration_ms": duration_ms,
            }
        )

        await db.auditlog.create(
            data={
                "tenant_id": tenant_id,
                "execution_id": execution.id,
                "actor": f"tool:{tool_id}",
                "action": "month_end_close:refresh",
                "reasoning_trace_json": {
                    "trace_id": trace_id,
                    "period": period,
                    "task_updates": task_updates,
                    "run_status": run_status,
                    "pending_transactions": pending_txn_count,
                    "pending_approvals": pending_approval_count,
                    "reconciliation_found": completed_recon is not None,
                    "duration_ms": duration_ms,
                },
            }
        )

        logger.info(
            "month_end_close_complete",
            extra={
                "tenant_id": tenant_id,
                "period": period,
                "run_status": run_status,
                "duration_ms": duration_ms,
            },
        )

        return {
            "close_run_id": updated_run.id,
            "period": period,
            "status": run_status,
            "tasks": updated_tasks,
            "execution_id": execution.id,
        }


async def run_month_end_close_scheduled(_ctx: dict) -> None:
    """Daily cron: auto-open and run month-end close for tenants whose configured day matches today."""
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    from app.queue.pool import get_queue_pool

    db = get_db()
    now_utc = datetime.now(UTC)
    pool = await get_queue_pool()

    tools = await db.tool.find_many(where={"type": "ai_accountant", "status": "active"})
    for tool in tools:
        try:
            cfg = tool.config_json or {}
            run_day = int(cfg.get("close_run_day_of_month", 1))

            tenant = await db.tenant.find_unique(where={"id": tool.tenant_id})
            tz_name = (tenant.timezone if tenant and tenant.timezone else None) or "UTC"
            try:
                tz = ZoneInfo(tz_name)
            except ZoneInfoNotFoundError:
                logger.warning("month_end_close_cron_unknown_tz tool=%s tz=%s — falling back to UTC", tool.id, tz_name)
                tz = ZoneInfo("UTC")

            local_now = now_utc.astimezone(tz)
            if local_now.day != run_day:
                continue

            period = local_now.strftime("%Y-%m")

            existing = await db.monthendcloserun.find_unique(
                where={"tenant_id_period": {"tenant_id": tool.tenant_id, "period": period}}
            )
            if existing:
                logger.info("month_end_close_scheduled_skip_existing tenant=%s period=%s", tool.tenant_id, period)
                continue

            close_run = await db.monthendcloserun.create(
                data={
                    "tenant_id": tool.tenant_id,
                    "period": period,
                    "status": "open",
                    "tasks_json": _build_default_tasks(),
                }
            )

            idem_key = f"month-end-close-auto:{tool.tenant_id}:{period}"
            await pool.enqueue_job(
                "run_month_end_close_job",
                close_run_id=close_run.id,
                tenant_id=tool.tenant_id,
                tool_id=tool.id,
                _job_id=idem_key,
            )
            logger.info(
                "month_end_close_scheduled_queued tenant=%s tool=%s period=%s",
                tool.tenant_id, tool.id, period,
            )
        except Exception as exc:
            logger.error(
                "month_end_close_cron_failed tenant=%s tool=%s: %s",
                tool.tenant_id, tool.id, type(exc).__name__,
            )


async def run_month_end_close_job(
    ctx: dict,
    close_run_id: str,
    tenant_id: str,
    tool_id: str,
) -> dict[str, Any]:
    """arq job wrapper for the Month-End Close Tool."""
    db = get_db()
    close_run = await db.monthendcloserun.find_unique(where={"id": close_run_id})
    if not close_run:
        raise ValueError(f"CloseRun {close_run_id} not found")

    tool = MonthEndCloseTool()
    try:
        result = await tool.run(
            period=close_run.period,
            tenant_id=tenant_id,
            tool_id=tool_id,
        )
        return result
    except Exception as exc:
        logger.error(
            "month_end_close_job_failed",
            extra={"close_run_id": close_run_id, "tenant_id": tenant_id, "error": str(exc)},
        )
        job_try = ctx.get("job_try", 1)
        if job_try >= 3:
            await push_to_dlq(
                job_id=str(ctx.get("job_id", "unknown")),
                function_name="run_month_end_close_job",
                error=str(exc),
            )
        raise
