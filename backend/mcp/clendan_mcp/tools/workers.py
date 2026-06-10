"""
tools/workers.py — Worker status and configuration tools.

Workers are Clendan's AI agents that run autonomously in the background.
These tools let you monitor, control, and inspect worker configuration
without opening the dashboard.
"""
from __future__ import annotations

from typing import Any

from clendan_mcp.auth import MCPError, api_get, api_patch, api_post

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


async def _find_worker_by_type(worker_type: str) -> dict[str, Any]:
    """Helper: fetch the worker record for a given type. Raises MCPError if not found."""
    if worker_type not in VALID_WORKER_TYPES:
        raise MCPError(
            f"Unknown worker type '{worker_type}'. "
            f"Valid types: {', '.join(sorted(VALID_WORKER_TYPES))}"
        )
    response = await api_get("/v1/workers")
    body = response.get("data", response)
    workers = body.get("workers", [])
    match = next((w for w in workers if w.get("type") == worker_type), None)
    if not match:
        raise MCPError(
            f"No worker of type '{worker_type}' is deployed in your account. "
            "Run list_workers() to see all deployed workers."
        )
    return match


async def list_workers() -> list[dict[str, Any]]:
    """
    List all deployed workers and their current status.

    Returns a list of workers, each with:
        id (str): Worker ID
        type (str): Worker type (e.g. "invoice_processing", "fraud_detection")
        autonomy_level (str): "auto" (no approval needed), "approve" (requires approval),
            or "suggest" (recommendation only)
        status (str): "active" (running) or "inactive" (paused)
        version (int): Config version number — increments on every change
        config_json (dict): Current worker configuration and policy thresholds

    Returns an empty list if no workers are deployed.
    """
    response = await api_get("/v1/workers")
    body = response.get("data", response)
    return body.get("workers", [])


async def get_worker_status(worker_type: str) -> dict[str, Any]:
    """
    Get detailed status of a specific worker by type.

    Args:
        worker_type: One of: invoice_processing, ai_accountant, receipt_processing,
            reconciliation, expense_control, collections, fraud_detection,
            treasury, revenue_recognition, credit_underwriting, compliance

    Returns:
        id (str): Worker ID
        type (str): Worker type
        autonomy_level (str): "auto" | "approve" | "suggest"
        status (str): "active" | "inactive"
        version (int): Current config version
        config_json (dict): Full worker config including policy thresholds,
            approval limits, currency allowlist, and override triggers
    """
    return await _find_worker_by_type(worker_type)


async def pause_worker(worker_type: str) -> dict[str, Any]:
    """
    Pause a running worker. It will stop processing new events until resumed.

    IMPORTANT: Pausing a worker stops all automated processing. Incoming invoices,
    transactions, or other events will queue up and not be processed until you
    call resume_worker(). Existing executions in progress will complete normally.

    Use this when you need to: temporarily stop automation before a period close,
    investigate unexpected behaviour, or make configuration changes.

    Args:
        worker_type: One of: invoice_processing, ai_accountant, receipt_processing,
            reconciliation, expense_control, collections, fraud_detection,
            treasury, revenue_recognition, credit_underwriting, compliance

    Returns:
        id (str): Worker ID
        type (str): Worker type
        status (str): "inactive" (paused)
        version (int): Incremented version number
    """
    worker = await _find_worker_by_type(worker_type)
    worker_id = worker["id"]

    if worker.get("status") == "inactive":
        raise MCPError(
            f"Worker '{worker_type}' is already paused. "
            "Call resume_worker() to restart it."
        )

    response = await api_patch(f"/v1/workers/{worker_id}/pause")
    return response.get("data", response)


async def resume_worker(worker_type: str) -> dict[str, Any]:
    """
    Resume a paused worker. It will begin processing events immediately.

    Args:
        worker_type: One of: invoice_processing, ai_accountant, receipt_processing,
            reconciliation, expense_control, collections, fraud_detection,
            treasury, revenue_recognition, credit_underwriting, compliance

    Returns:
        id (str): Worker ID
        type (str): Worker type
        status (str): "active" (running)
        version (int): Incremented version number
    """
    worker = await _find_worker_by_type(worker_type)
    worker_id = worker["id"]

    if worker.get("status") == "active":
        raise MCPError(
            f"Worker '{worker_type}' is already active. "
            "Call pause_worker() to stop it."
        )

    response = await api_patch(f"/v1/workers/{worker_id}/pause")
    return response.get("data", response)


async def get_policy_rules(worker_type: str) -> dict[str, Any]:
    """
    Get the current policy rules for a worker.

    Policy rules control how the worker makes decisions: what thresholds trigger
    approval requests, which currencies are allowed, what supplier checks run,
    and when the worker should escalate to a human override.

    Args:
        worker_type: One of: invoice_processing, ai_accountant, receipt_processing,
            reconciliation, expense_control, collections, fraud_detection,
            treasury, revenue_recognition, credit_underwriting, compliance

    Returns:
        worker_type (str): The worker type
        autonomy_level (str): "auto" | "approve" | "suggest"
        version (int): Config version (rules increment this when changed)
        policy (dict): Full policy configuration. Contents vary by worker type
            but typically include:
            - approval_threshold_minor: Amount above which approval is required
            - auto_approve_limit_minor: Amount below which auto-approval is allowed
            - currency_allowlist: Accepted currency codes
            - supplier_verification: Supplier check settings
            - human_override_triggers: Conditions that always require human approval
    """
    worker = await _find_worker_by_type(worker_type)
    return {
        "worker_type": worker.get("type"),
        "autonomy_level": worker.get("autonomy_level"),
        "version": worker.get("version"),
        "policy": worker.get("config_json", {}),
    }
