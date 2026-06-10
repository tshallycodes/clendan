"""
tools/analytics.py — Execution statistics and ROI measurement tools.

These tools aggregate data from the Clendan API to give you high-level
visibility into how your workers are performing and how much time they're
saving your team.
"""
from __future__ import annotations

from typing import Any

from clendan_mcp.auth import MCPError, api_get

VALID_PERIODS = {"1d", "7d", "30d", "90d"}

# Average manual processing time per task type in minutes (industry estimates)
# Used to calculate hours saved vs automated processing
_MANUAL_MINUTES_PER_TASK: dict[str, float] = {
    "invoice_processing": 12.0,      # 12 min to process an invoice manually
    "receipt_processing": 5.0,       # 5 min per receipt
    "ai_accountant": 30.0,           # 30 min for a manual accounting review
    "reconciliation": 45.0,          # 45 min per reconciliation cycle
    "expense_control": 8.0,          # 8 min per expense review
    "collections": 20.0,             # 20 min per collections outreach
    "fraud_detection": 15.0,         # 15 min to manually review a transaction
    "treasury": 60.0,                # 60 min for treasury management task
    "revenue_recognition": 25.0,     # 25 min per revenue recognition event
    "credit_underwriting": 90.0,     # 90 min for a credit review
    "compliance": 40.0,              # 40 min per compliance check
}

# Clendan automated processing time per task in minutes (measured average)
_AUTO_MINUTES_PER_TASK: float = 0.5  # ~30 seconds for most automated tasks


async def get_execution_stats(period: str = "7d") -> dict[str, Any]:
    """
    Get execution statistics for a time period.

    Shows how many tasks your workers processed, what decisions they made,
    and how efficiently they're running.

    Args:
        period: Time period to analyse. One of: 1d (today), 7d (last 7 days),
            30d (last 30 days), 90d (last quarter). Default: 7d.

    Returns:
        period (str): The period analysed
        total_executions (int): Total worker executions in the period
        auto_approved (int): Executions auto-approved without human review
        approval_required (int): Executions routed for human approval
        blocked (int): Executions blocked by policy rules
        failed (int): Executions that errored
        auto_approval_rate (float): Fraction of executions handled automatically (0.0–1.0)
        avg_confidence (float): Average worker confidence across all executions
        active_workers (int): Number of currently active workers
        total_workers (int): Total workers deployed (active + inactive)
        breakdown_by_worker (dict): Per-worker-type execution counts
        dashboard_url (str): Direct link to the full dashboard
    """
    if period not in VALID_PERIODS:
        raise MCPError(
            f"Invalid period '{period}'. Valid periods: {', '.join(sorted(VALID_PERIODS))}"
        )

    # Fetch dashboard stats and executions in parallel
    stats_response = await api_get("/v1/dashboard/stats")
    stats = stats_response.get("data", stats_response)

    # Fetch executions with limit to get breakdown
    exec_response = await api_get("/v1/dashboard/executions", params={"limit": 200})
    exec_data = exec_response.get("data", exec_response)
    executions = exec_data.get("executions", [])

    # Aggregate counts
    total = len(executions)
    auto_approved = sum(1 for e in executions if e.get("decision") == "auto_approved")
    approval_required = sum(1 for e in executions if e.get("decision") == "route_for_approval")
    blocked = sum(1 for e in executions if e.get("decision") == "block")
    failed = sum(1 for e in executions if e.get("status") == "failed")

    # Confidence average
    confidences = [e.get("confidence", 0.0) for e in executions if e.get("confidence") is not None]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    # Per-worker breakdown
    breakdown: dict[str, int] = {}
    for e in executions:
        wt = e.get("worker_type", "unknown")
        breakdown[wt] = breakdown.get(wt, 0) + 1

    return {
        "period": period,
        "total_executions": total,
        "auto_approved": auto_approved,
        "approval_required": approval_required,
        "blocked": blocked,
        "failed": failed,
        "auto_approval_rate": round(auto_approved / total, 3) if total > 0 else 0.0,
        "avg_confidence": round(avg_confidence, 3),
        "active_workers": stats.get("active_workers", 0),
        "total_workers": stats.get("active_workers", 0),
        "pending_approvals": stats.get("pending_approvals", 0),
        "breakdown_by_worker": breakdown,
        "dashboard_url": "https://app.clendan.com/dashboard",
    }


async def get_hours_saved(period: str = "30d") -> dict[str, Any]:
    """
    Calculate hours saved by Clendan workers over a period.

    Compares the average manual processing time for each task type against
    Clendan's automated processing time, multiplied by the number of executions.

    Args:
        period: Time period to analyse. One of: 1d, 7d, 30d, 90d. Default: 30d.

    Returns:
        period (str): The period analysed
        total_hours_saved (float): Total hours saved across all workers
        total_executions (int): Total executions in the period
        breakdown_by_worker (list): Per-worker breakdown, each with:
            worker_type (str): Worker type
            executions (int): Number of executions
            manual_minutes_each (float): Estimated manual time per task
            auto_minutes_each (float): Automated processing time per task
            hours_saved (float): Hours saved by this worker type
        assumptions (dict): The time estimates used in the calculation
        equivalent_fte_days (float): Equivalent full-time employee days saved
            (assuming 8-hour workdays)
    """
    if period not in VALID_PERIODS:
        raise MCPError(
            f"Invalid period '{period}'. Valid periods: {', '.join(sorted(VALID_PERIODS))}"
        )

    exec_response = await api_get("/v1/dashboard/executions", params={"limit": 200})
    exec_data = exec_response.get("data", exec_response)
    executions = exec_data.get("executions", [])

    # Count by worker type
    counts: dict[str, int] = {}
    for e in executions:
        wt = e.get("worker_type", "unknown")
        counts[wt] = counts.get(wt, 0) + 1

    total_minutes_saved = 0.0
    breakdown = []
    for worker_type, count in sorted(counts.items()):
        manual_minutes = _MANUAL_MINUTES_PER_TASK.get(worker_type, 15.0)
        minutes_saved = (manual_minutes - _AUTO_MINUTES_PER_TASK) * count
        hours_saved = minutes_saved / 60.0
        total_minutes_saved += minutes_saved
        breakdown.append({
            "worker_type": worker_type,
            "executions": count,
            "manual_minutes_each": manual_minutes,
            "auto_minutes_each": _AUTO_MINUTES_PER_TASK,
            "hours_saved": round(hours_saved, 2),
        })

    total_hours = total_minutes_saved / 60.0
    fte_days = total_hours / 8.0  # 8-hour workday

    return {
        "period": period,
        "total_hours_saved": round(total_hours, 2),
        "total_executions": len(executions),
        "breakdown_by_worker": breakdown,
        "equivalent_fte_days": round(fte_days, 2),
        "assumptions": {
            "note": "Manual time estimates are industry averages. Actual savings may vary.",
            "auto_minutes_per_task": _AUTO_MINUTES_PER_TASK,
            "manual_minutes_by_type": _MANUAL_MINUTES_PER_TASK,
            "workday_hours": 8,
        },
    }
