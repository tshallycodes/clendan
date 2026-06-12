"""
server.py — Clendan MCP Server entry point.

Registers all 21 tools and starts the stdio transport. Run with:
    python -m clendan_mcp.server
or via uvx:
    uvx clendan-mcp

Requires CLENDAN_API_KEY environment variable.
"""
from __future__ import annotations

import asyncio

from mcp.server import Server
from mcp.server.stdio import stdio_server

from clendan_mcp.tools.invoices import parse_invoice, run_invoice_tool
from clendan_mcp.tools.approvals import (
    get_pending_approvals,
    approve_execution,
    reject_execution,
    get_approval_detail,
)
from clendan_mcp.tools.audit import get_audit_trail, get_execution_detail
from clendan_mcp.tools.tools import (
    list_tools,
    get_tool_status,
    pause_tool,
    resume_tool,
    get_policy_rules,
)
from clendan_mcp.tools.integrations import (
    list_integrations,
    get_integration_status,
    trigger_sync,
)
from clendan_mcp.tools.api_tools import (
    score_fraud,
    reconcile_datasets,
    extract_contract_data,
)
from clendan_mcp.tools.analytics import get_execution_stats, get_hours_saved

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

app = Server("clendan")

# --- Financial operations ---
app.tool()(parse_invoice)
app.tool()(run_invoice_tool)
app.tool()(score_fraud)
app.tool()(reconcile_datasets)
app.tool()(extract_contract_data)

# --- Approval queue ---
app.tool()(get_pending_approvals)
app.tool()(approve_execution)
app.tool()(reject_execution)
app.tool()(get_approval_detail)

# --- Audit trail ---
app.tool()(get_audit_trail)
app.tool()(get_execution_detail)

# --- Tools ---
app.tool()(list_tools)
app.tool()(get_tool_status)
app.tool()(pause_tool)
app.tool()(resume_tool)
app.tool()(get_policy_rules)

# --- Integrations ---
app.tool()(list_integrations)
app.tool()(get_integration_status)
app.tool()(trigger_sync)

# --- Analytics ---
app.tool()(get_execution_stats)
app.tool()(get_hours_saved)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


def main() -> None:
    """Entry point for `clendan-mcp` console script and `python -m clendan_mcp.server`."""
    asyncio.run(_run())


if __name__ == "__main__":
    main()
