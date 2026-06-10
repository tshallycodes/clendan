"""
tools/audit.py — Audit trail and execution detail tools.

Clendan's audit trail is immutable — records cannot be modified or deleted.
These tools provide read-only access to it.
"""
from __future__ import annotations

from typing import Any

from clendan_mcp.auth import MCPError, api_get

VALID_WORKER_TYPES = {
    "invoice_processing",
    "ai_accountant",
    "receipt_processing",
    "reconciliation",
    "expense_control",
    "collections",
    "fraud_detection",
    "treasury",
    "revenue_recognition",
    "credit_underwriting",
    "compliance",
}

VALID_STATUSES = {"auto", "approved", "rejected", "blocked", "pending", "failed"}


async def get_audit_trail(
    worker_type: str | None = None,
    status: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    Query the immutable audit trail.

    The audit trail records every worker execution and human action. Records
    are permanently stored and cannot be modified or deleted.

    Args:
        worker_type: Filter by worker type. Valid values:
            invoice_processing, ai_accountant, receipt_processing,
            reconciliation, expense_control, collections, fraud_detection,
            treasury, revenue_recognition, credit_underwriting, compliance.
            Leave empty to see all worker types.
        status: Filter by execution status. Valid values:
            auto, approved, rejected, blocked, pending, failed.
            Leave empty to see all statuses.
        from_date: Start of date range in ISO 8601 format (YYYY-MM-DD).
        to_date: End of date range in ISO 8601 format (YYYY-MM-DD).
        limit: Max records to return (1–200, default 20).

    Returns a list of audit entries, each with:
        id (str): Audit log entry ID
        actor (str): Who/what performed the action (e.g. "worker:invoice_processing")
        action (str): What action was taken
        model_version (str): AI model version used (or "human" for manual actions)
        created_at (str): ISO 8601 timestamp
        execution_id (str | null): Associated execution ID (use in get_execution_detail)
        reasoning_trace_json (dict | null): Structured reasoning from the worker
    """
    if worker_type and worker_type not in VALID_WORKER_TYPES:
        raise MCPError(
            f"Invalid worker_type '{worker_type}'. "
            f"Valid types: {', '.join(sorted(VALID_WORKER_TYPES))}"
        )
    if status and status not in VALID_STATUSES:
        raise MCPError(
            f"Invalid status '{status}'. "
            f"Valid statuses: {', '.join(sorted(VALID_STATUSES))}"
        )
    if not (1 <= limit <= 200):
        raise MCPError("limit must be between 1 and 200.")

    params: dict[str, Any] = {"limit": limit}
    if worker_type:
        params["worker_type"] = worker_type
    if status:
        params["status"] = status
    if from_date:
        params["from_date"] = from_date
    if to_date:
        params["to_date"] = to_date

    response = await api_get("/v1/dashboard/audit", params=params)
    body = response.get("data", response)
    return body.get("entries", [])


async def get_execution_detail(trace_id: str) -> dict[str, Any]:
    """
    Get the full detail of a specific execution by trace ID.

    Returns a complete record of everything that happened during a worker
    execution: input data, every policy rule evaluated (pass/fail), the final
    decision, confidence score, actions taken, and the full ordered reasoning
    trace from the AI model.

    Args:
        trace_id: The execution ID. Found in audit trail entries as 'execution_id',
                  or in the output of parse_invoice / run_invoice_worker.

    Returns:
        execution (dict):
            id (str): Execution ID
            worker_id (str): The worker that ran
            decision (str): Final decision
            confidence (float): Confidence score 0.0–1.0
            status (str): Execution status
            created_at (str): When the execution started
        reasoning_traces (list): Ordered list of reasoning steps, each with:
            audit_id (str): Audit log entry ID
            actor (str): Who generated this trace entry
            action (str): What this step did
            model_version (str): Model version
            created_at (str): When this step occurred
            reasoning_trace_json (dict): Structured reasoning data
    """
    if not trace_id or not trace_id.strip():
        raise MCPError(
            "trace_id is required. Find execution IDs in get_audit_trail() results "
            "under the 'execution_id' field."
        )

    response = await api_get(f"/v1/decisions/{trace_id.strip()}/explain")
    return response.get("data", response)
