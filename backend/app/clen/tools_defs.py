"""
Anthropic tool_use schema definitions for Clen account mode.
Imported by tools.py - kept separate to stay within the 500-line limit.
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
        "description": "Returns recent audit log entries, optionally filtered by tool type and status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tool_type": {"type": "string", "description": "Filter by tool type. Optional."},
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
        "name": "get_financial_summary",
        "description": (
            "Returns the money position across the connected books: total outstanding "
            "receivables (money owed to you), total outstanding payables (money you owe), and "
            "how much of each is overdue. Use for 'what's my position', 'how much do I owe', "
            "'who owes me', 'am I cash positive'."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "list_overdue_invoices",
        "description": (
            "Lists the oldest overdue customer invoices (receivables past their due date). "
            "Use for 'what's overdue', 'who hasn't paid', or before chasing customers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max invoices to return (default 10, max 50).", "default": 10},
            },
            "required": [],
        },
    },
    {
        "name": "list_tools",
        "description": "Lists all tools configured for this organisation.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_tool_status",
        "description": "Returns the current status and configuration of a specific tool.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tool_type": {"type": "string", "description": "Tool type to look up (e.g. invoice_processing)."},
            },
            "required": ["tool_type"],
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
        "name": "pause_tool",
        "description": (
            "ACTION: Pauses (deactivates) a tool by type. "
            "REQUIRES explicit user confirmation before calling. "
            "Writes to audit log before updating tool status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tool_type": {"type": "string", "description": "Tool type to pause (e.g. invoice_processing)."},
            },
            "required": ["tool_type"],
        },
    },
    {
        "name": "run_automation",
        "description": (
            "ACTION: Runs a deployed automation now (e.g. the user asks to 'run spend control' "
            "or 'reconcile now'). This does NOT run immediately - it PROPOSES the action and "
            "returns a confirmation card the user must approve in the UI before it executes. "
            "Call this when the user wants to trigger a tool/automation on demand, then tell "
            "them you've prepared it and to confirm."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tool_type": {"type": "string", "description": "Automation/tool type to run (e.g. spend_control, reconciliation, ar_collections, tax_compliance)."},
            },
            "required": ["tool_type"],
        },
    },
]
