"""
tools/approvals.py — Approval queue tools.

Lets Claude (or any MCP client) list pending approvals and approve or
reject them without opening the Clendan dashboard.
"""
from __future__ import annotations

from typing import Any

from clendan_mcp.auth import MCPError, api_get, api_post


async def get_pending_approvals() -> list[dict[str, Any]]:
    """
    List all executions currently waiting for human approval.

    Returns a list of pending approval items. Each item includes:
        id (str): Approval ID — use this in approve_execution or reject_execution
        execution_id (str): The tool execution that needs review
        status (str): Always "pending"
        requested_at (str): ISO 8601 timestamp when approval was requested
        expires_at (str): ISO 8601 timestamp when approval expires (after which it auto-rejects)
        decision (str): The tool's proposed decision
        confidence (float): Tool confidence score 0.0–1.0

    Returns an empty list if no approvals are pending.
    """
    response = await api_get("/v1/dashboard/approvals", params={"limit": 100})
    body = response.get("data", response)
    return body.get("approvals", [])


async def approve_execution(approval_id: str, note: str = "") -> dict[str, Any]:
    """
    Approve a pending execution. The tool will complete the action immediately.

    IMPORTANT: This action is irreversible. The tool will proceed to execute
    whatever action it was waiting to take (e.g. posting a payment, creating a
    bill). Only approve if you have reviewed the details via get_approval_detail().

    Args:
        approval_id: The approval ID from get_pending_approvals() — starts with "appr_"
        note: Optional note to record in the audit trail (recommended)

    Returns:
        approval_id (str): The approved approval ID
        status (str): "approved"
        execution_id (str): The execution that was approved
        responded_at (str): Timestamp of the approval
    """
    if not approval_id or not approval_id.strip():
        raise MCPError("approval_id is required. Get it from get_pending_approvals().")

    response = await api_post(
        f"/v1/approvals/{approval_id.strip()}/respond",
        data={"action": "approve", "note": note or ""},
    )
    return response.get("data", response)


async def reject_execution(approval_id: str, reason: str) -> dict[str, Any]:
    """
    Reject a pending execution. The action will NOT be taken.

    IMPORTANT: The rejection reason is permanently recorded in the audit trail
    and cannot be edited. Be clear and specific — this is the compliance record.

    Args:
        approval_id: The approval ID from get_pending_approvals() — starts with "appr_"
        reason: Required. Why you are rejecting this execution. Must be non-empty.

    Returns:
        approval_id (str): The rejected approval ID
        status (str): "rejected"
        execution_id (str): The execution that was rejected
        responded_at (str): Timestamp of the rejection
    """
    if not approval_id or not approval_id.strip():
        raise MCPError("approval_id is required. Get it from get_pending_approvals().")
    if not reason or not reason.strip():
        raise MCPError(
            "reason is required when rejecting. "
            "Provide a clear explanation — it will be recorded permanently in the audit trail."
        )

    response = await api_post(
        f"/v1/approvals/{approval_id.strip()}/respond",
        data={"action": "reject", "reason": reason.strip()},
    )
    return response.get("data", response)


async def get_approval_detail(approval_id: str) -> dict[str, Any]:
    """
    Get full details of a pending approval including the complete reasoning trace.

    Use this before approving or rejecting to understand why the tool escalated.
    Returns the tool's full reasoning, policy evaluation results, and all
    input data that was used in the decision.

    Args:
        approval_id: The approval ID from get_pending_approvals() — starts with "appr_"

    Returns:
        approval (dict): The approval record with status, timing, and expiry
        execution (dict): The tool execution that triggered this approval
        reasoning_traces (list): Ordered list of reasoning steps from the tool,
            each with actor, action, model_version, and reasoning_trace_json
        input_data (dict): The original data the tool processed
    """
    if not approval_id or not approval_id.strip():
        raise MCPError("approval_id is required. Get it from get_pending_approvals().")

    # First fetch the approval to get execution_id
    # The approvals list endpoint gives us execution_id
    approvals_response = await api_get("/v1/dashboard/approvals", params={"limit": 200})
    approvals_body = approvals_response.get("data", approvals_response)
    approvals = approvals_body.get("approvals", [])

    target = next(
        (a for a in approvals if a.get("id") == approval_id.strip()),
        None,
    )
    if not target:
        raise MCPError(
            f"Approval '{approval_id}' not found. "
            "It may have already been acted on or expired. "
            "Run get_pending_approvals() to see current pending items."
        )

    execution_id = target.get("execution_id")
    if not execution_id:
        raise MCPError(f"Approval '{approval_id}' has no associated execution.")

    # Fetch the full decision explanation
    detail_response = await api_get(f"/v1/decisions/{execution_id}/explain")
    detail_body = detail_response.get("data", detail_response)

    return {
        "approval": target,
        "execution": detail_body.get("execution", {}),
        "reasoning_traces": detail_body.get("reasoning_traces", []),
    }
