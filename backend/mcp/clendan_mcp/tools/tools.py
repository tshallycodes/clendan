"""
tools/tools.py — Tool status and configuration tools.

Tools are Clendan's AI agents that run autonomously in the background.
These tools let you monitor, control, and inspect tool configuration
without opening the dashboard.
"""
from __future__ import annotations

from typing import Any

from clendan_mcp.auth import MCPError, api_get, api_patch, api_post

VALID_TOOL_TYPES = {
    "invoice_processing",
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


async def _find_tool_by_type(tool_type: str) -> dict[str, Any]:
    """Helper: fetch the tool record for a given type. Raises MCPError if not found."""
    if tool_type not in VALID_TOOL_TYPES:
        raise MCPError(
            f"Unknown tool type '{tool_type}'. "
            f"Valid types: {', '.join(sorted(VALID_TOOL_TYPES))}"
        )
    response = await api_get("/tools")
    body = response.get("data", response)
    tools = body.get("tools", [])
    match = next((w for w in tools if w.get("type") == tool_type), None)
    if not match:
        raise MCPError(
            f"No tool of type '{tool_type}' is deployed in your account. "
            "Run list_tools() to see all deployed tools."
        )
    return match


async def list_tools() -> list[dict[str, Any]]:
    """
    List all deployed tools and their current status.

    Returns a list of tools, each with:
        id (str): Tool ID
        type (str): Tool type (e.g. "invoice_processing", "fraud_detection")
        autonomy_level (str): "auto" (no approval needed) or "approve" (requires approval)
        status (str): "active" (running) or "inactive" (paused)
        version (int): Config version number — increments on every change
        config_json (dict): Current tool configuration and policy thresholds

    Returns an empty list if no tools are deployed.
    """
    response = await api_get("/tools")
    body = response.get("data", response)
    return body.get("tools", [])


async def get_tool_status(tool_type: str) -> dict[str, Any]:
    """
    Get detailed status of a specific tool by type.

    Args:
        tool_type: One of: invoice_processing, receipt_processing,
            reconciliation, expense_control, collections, fraud_detection,
            treasury, revenue_recognition, credit_underwriting, compliance

    Returns:
        id (str): Tool ID
        type (str): Tool type
        autonomy_level (str): "auto" | "approve"
        status (str): "active" | "inactive"
        version (int): Current config version
        config_json (dict): Full tool config including policy thresholds,
            approval limits, currency allowlist, and override triggers
    """
    return await _find_tool_by_type(tool_type)


async def pause_tool(tool_type: str) -> dict[str, Any]:
    """
    Pause a running tool. It will stop processing new events until resumed.

    IMPORTANT: Pausing a tool stops all automated processing. Incoming invoices,
    transactions, or other events will queue up and not be processed until you
    call resume_tool(). Existing executions in progress will complete normally.

    Use this when you need to: temporarily stop automation before a period close,
    investigate unexpected behaviour, or make configuration changes.

    Args:
        tool_type: One of: invoice_processing, receipt_processing,
            reconciliation, expense_control, collections, fraud_detection,
            treasury, revenue_recognition, credit_underwriting, compliance

    Returns:
        id (str): Tool ID
        type (str): Tool type
        status (str): "inactive" (paused)
        version (int): Incremented version number
    """
    tool = await _find_tool_by_type(tool_type)
    tool_id = tool["id"]

    if tool.get("status") == "inactive":
        raise MCPError(
            f"Tool '{tool_type}' is already paused. "
            "Call resume_tool() to restart it."
        )

    response = await api_patch(f"/tools/{tool_id}/pause")
    return response.get("data", response)


async def resume_tool(tool_type: str) -> dict[str, Any]:
    """
    Resume a paused tool. It will begin processing events immediately.

    Args:
        tool_type: One of: invoice_processing, receipt_processing,
            reconciliation, expense_control, collections, fraud_detection,
            treasury, revenue_recognition, credit_underwriting, compliance

    Returns:
        id (str): Tool ID
        type (str): Tool type
        status (str): "active" (running)
        version (int): Incremented version number
    """
    tool = await _find_tool_by_type(tool_type)
    tool_id = tool["id"]

    if tool.get("status") == "active":
        raise MCPError(
            f"Tool '{tool_type}' is already active. "
            "Call pause_tool() to stop it."
        )

    response = await api_patch(f"/tools/{tool_id}/pause")
    return response.get("data", response)


async def get_policy_rules(tool_type: str) -> dict[str, Any]:
    """
    Get the current policy rules for a tool.

    Policy rules control how the tool makes decisions: what thresholds trigger
    approval requests, which currencies are allowed, what supplier checks run,
    and when the tool should escalate to a human override.

    Args:
        tool_type: One of: invoice_processing, receipt_processing,
            reconciliation, expense_control, collections, fraud_detection,
            treasury, revenue_recognition, credit_underwriting, compliance

    Returns:
        tool_type (str): The tool type
        autonomy_level (str): "auto" | "approve"
        version (int): Config version (rules increment this when changed)
        policy (dict): Full policy configuration. Contents vary by tool type
            but typically include:
            - approval_threshold_minor: Amount above which approval is required
            - auto_approve_limit_minor: Amount below which auto-approval is allowed
            - currency_allowlist: Accepted currency codes
            - supplier_verification: Supplier check settings
            - human_override_triggers: Conditions that always require human approval
    """
    tool = await _find_tool_by_type(tool_type)
    return {
        "tool_type": tool.get("type"),
        "autonomy_level": tool.get("autonomy_level"),
        "version": tool.get("version"),
        "policy": tool.get("config_json", {}),
    }
