"""
Anthropic tool_use schema definitions for Clen account mode.
Imported by tools.py — kept separate to stay within the 500-line limit.
"""

ACCOUNT_TOOLS: list[dict] = [
    {
        "name": "get_pending_approvals",
        "description": "Returns all pending approval requests for this organisation.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_execution_detail",
        "description": "Returns full detail for a single agent execution by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "execution_id": {"type": "string", "description": "The execution ID to look up."},
            },
            "required": ["execution_id"],
        },
    },
    {
        "name": "get_audit_trail",
        "description": "Returns recent audit log entries, optionally filtered by worker type and status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "worker_type": {"type": "string", "description": "Filter by worker type. Optional."},
                "status": {"type": "string", "description": "Filter by execution status. Optional."},
                "limit": {"type": "integer", "description": "Max entries to return (default 10, max 50).", "default": 10},
            },
            "required": [],
        },
    },
    {
        "name": "get_execution_stats",
        "description": "Returns execution counts grouped by decision for a time period.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "description": "Time period: '1d', '7d', '30d' (default '7d').", "default": "7d"},
            },
            "required": [],
        },
    },
    {
        "name": "list_workers",
        "description": "Lists all workers configured for this organisation.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_worker_status",
        "description": "Returns the current status and configuration of a specific worker.",
        "input_schema": {
            "type": "object",
            "properties": {
                "worker_type": {"type": "string", "description": "Worker type to look up (e.g. invoice_processing)."},
            },
            "required": ["worker_type"],
        },
    },
    {
        "name": "list_integrations",
        "description": "Lists all integrations for this organisation and their connection status.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_integration_status",
        "description": "Returns the connection status and last sync time for a specific integration.",
        "input_schema": {
            "type": "object",
            "properties": {
                "integration_type": {"type": "string", "description": "Integration type (e.g. quickbooks, xero, plaid)."},
            },
            "required": ["integration_type"],
        },
    },
    {
        "name": "approve_execution",
        "description": (
            "ACTION: Approves a pending execution approval. "
            "REQUIRES explicit user confirmation before calling. "
            "Writes to audit log before updating approval status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "approval_id": {"type": "string", "description": "The approval ID to approve."},
                "note": {"type": "string", "description": "Optional note.", "default": ""},
            },
            "required": ["approval_id"],
        },
    },
    {
        "name": "reject_execution",
        "description": (
            "ACTION: Rejects a pending execution approval. "
            "REQUIRES explicit user confirmation before calling. "
            "Writes to audit log before updating approval status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "approval_id": {"type": "string", "description": "The approval ID to reject."},
                "reason": {"type": "string", "description": "Reason for rejection."},
            },
            "required": ["approval_id", "reason"],
        },
    },
    {
        "name": "pause_worker",
        "description": (
            "ACTION: Pauses (deactivates) a worker by type. "
            "REQUIRES explicit user confirmation before calling. "
            "Writes to audit log before updating worker status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "worker_type": {"type": "string", "description": "Worker type to pause (e.g. invoice_processing)."},
            },
            "required": ["worker_type"],
        },
    },
]
