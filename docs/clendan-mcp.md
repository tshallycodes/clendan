# Clendan MCP Server
# Build this after: Invoice Parser API stable, Invoice Processing Worker wired,
# Authentication working end to end.

---

## What This Is

A Model Context Protocol (MCP) server that exposes Clendan's financial
execution capabilities as tools any MCP-compatible client can call.
Developers and finance teams connect Claude (or any MCP client) directly
to their Clendan account and interact with it conversationally or
programmatically — without writing REST API code.

---

## Why We're Building This

- **Distribution** — Listed on mcpmarket.com and Anthropic's MCP directory.
  Developers searching for finance tools find Clendan.
- **Power users** — CTOs and technical finance managers build internal
  workflows on top of Clendan using Claude + MCP.
- **Competitive moat** — Bluecopa, Tipalti, and Arahi have no MCP.
  Being MCP-native is a technical credibility signal in 2026.
- **Internal use** — We use the Clendan MCP with Claude Code to query
  our own platform while building it.

---

## Stack

- Language: Python 3.12
- MCP SDK: `mcp` (Anthropic's official Python SDK)
- Auth: Clendan API key (passed as env var or MCP config)
- Transport: stdio (local) + SSE (remote/hosted)
- Hosting: Railway (same as backend)

---

## File Structure

```
backend/
└── mcp/
    ├── server.py              # MCP server entry point — registers all tools
    ├── auth.py                # API key validation and request auth
    ├── client.py              # HTTP client for calling Clendan REST API
    ├── tools/
    │   ├── __init__.py
    │   ├── invoices.py        # Invoice parsing and processing tools
    │   ├── approvals.py       # Approval queue tools
    │   ├── audit.py           # Audit trail and execution detail tools
    │   ├── workers.py         # Worker status and configuration tools
    │   ├── integrations.py    # Integration status tools
    │   ├── api_tools.py       # Standalone API tool wrappers
    │   └── policy.py          # Policy rule tools
    └── README.md              # How to connect and use the MCP
```

---

## Tools to Expose

### Financial Operations

```python
@mcp.tool()
async def parse_invoice(file_path: str) -> dict:
    """
    Parse an invoice document and extract structured data.
    Accepts a local file path to a PDF, PNG, JPG, or TIFF.
    Returns vendor, invoice number, line items, amounts, due date,
    VAT, PO number, and confidence score.
    """

@mcp.tool()
async def run_invoice_worker(invoice_data: dict) -> dict:
    """
    Run the Invoice Processing Worker on parsed invoice data.
    The worker validates the invoice, checks policy rules, and either
    auto-approves, routes for approval, or blocks the invoice.
    Returns decision, confidence, reasoning trace, and actions taken.
    """

@mcp.tool()
async def score_fraud(
    transaction_id: str,
    amount_minor: int,
    currency: str,
    counterparty: str,
    transaction_type: str
) -> dict:
    """
    Score a transaction for fraud risk.
    Returns risk score (0-1), risk level (low/medium/high/critical),
    detected signals, recommended action, and reasoning.
    """

@mcp.tool()
async def reconcile_datasets(
    source_records: list,
    target_records: list,
    period_start: str,
    period_end: str
) -> dict:
    """
    Reconcile two financial datasets.
    Returns matched records, unmatched records, flagged discrepancies,
    and confidence scores. Useful for month-end close.
    """

@mcp.tool()
async def extract_contract_data(file_path: str) -> dict:
    """
    Extract structured data from a contract PDF.
    Returns counterparty, payment terms, renewal date, obligations,
    amounts, and governing law.
    """
```

### Approval Queue

```python
@mcp.tool()
async def get_pending_approvals() -> list:
    """
    List all executions currently waiting for human approval.
    Returns approval ID, vendor, amount, worker type, time waiting,
    expiry time, and reasoning summary for each pending item.
    """

@mcp.tool()
async def approve_execution(
    approval_id: str,
    note: str = ""
) -> dict:
    """
    Approve a pending execution.
    The worker will complete the action immediately after approval.
    Optionally include a note for the audit trail.
    """

@mcp.tool()
async def reject_execution(
    approval_id: str,
    reason: str
) -> dict:
    """
    Reject a pending execution.
    The action will not be taken. Reason is logged to the audit trail.
    Reason is required.
    """

@mcp.tool()
async def get_approval_detail(approval_id: str) -> dict:
    """
    Get full details of a pending approval including the complete
    reasoning trace, policy evaluation results, and input data.
    Use this before approving or rejecting to understand why the
    worker escalated.
    """
```

### Audit Trail

```python
@mcp.tool()
async def get_audit_trail(
    worker_type: str = None,
    status: str = None,
    from_date: str = None,
    to_date: str = None,
    limit: int = 20
) -> list:
    """
    Query the immutable audit trail.
    Filter by worker type (invoice_processing, accountant, etc.),
    status (auto, approved, rejected, blocked), and date range.
    Returns execution summaries with trace IDs.
    Audit records cannot be modified or deleted.
    """

@mcp.tool()
async def get_execution_detail(trace_id: str) -> dict:
    """
    Get the full detail of a specific execution by trace ID.
    Returns input data, policy evaluation results (each rule pass/fail),
    decision, confidence score, actions taken, duration, and
    full reasoning trace.
    """
```

### Workers

```python
@mcp.tool()
async def list_workers() -> list:
    """
    List all deployed workers and their current status.
    Returns worker name, type, autonomy level, status (running/paused/error),
    executions today, last action timestamp, and connected integrations.
    """

@mcp.tool()
async def get_worker_status(worker_type: str) -> dict:
    """
    Get detailed status of a specific worker.
    Returns current config, autonomy level, policy thresholds,
    execution counts, error rate, and last execution detail.
    """

@mcp.tool()
async def pause_worker(worker_type: str) -> dict:
    """
    Pause a running worker. It will stop processing new events
    until resumed. Existing executions in the queue complete normally.
    """

@mcp.tool()
async def resume_worker(worker_type: str) -> dict:
    """
    Resume a paused worker.
    """

@mcp.tool()
async def get_policy_rules(worker_type: str) -> dict:
    """
    Get the current policy rules for a worker.
    Returns approval thresholds, supplier verification settings,
    currency allowlist, and human override triggers.
    """
```

### Integrations

```python
@mcp.tool()
async def list_integrations() -> list:
    """
    List all integrations and their connection status.
    Returns integration name, type, status (connected/error/disconnected),
    last sync timestamp, and records synced count.
    """

@mcp.tool()
async def get_integration_status(integration_type: str) -> dict:
    """
    Get detailed status of a specific integration.
    Returns connection status, last sync, sync log (last 10 entries),
    error details if any, and connected data counts.
    """

@mcp.tool()
async def trigger_sync(integration_type: str) -> dict:
    """
    Manually trigger a resync for an integration.
    Returns job ID to track sync progress.
    """
```

### Analytics

```python
@mcp.tool()
async def get_execution_stats(
    period: str = "7d"
) -> dict:
    """
    Get execution statistics for a time period.
    Period options: 1d, 7d, 30d, 90d.
    Returns total executions, auto-approved count, approval-required count,
    blocked count, average confidence, average duration, error rate,
    and breakdown by worker type.
    """

@mcp.tool()
async def get_hours_saved(period: str = "30d") -> dict:
    """
    Calculate hours saved by Clendan workers over a period.
    Based on average manual processing time per task type vs
    automated processing time. Returns total hours saved and
    breakdown by worker.
    """
```

---

## server.py Structure

```python
from mcp.server import Server
from mcp.server.stdio import stdio_server
import asyncio

from .auth import get_api_key
from .tools.invoices import parse_invoice, run_invoice_worker
from .tools.approvals import (
    get_pending_approvals,
    approve_execution,
    reject_execution,
    get_approval_detail
)
from .tools.audit import get_audit_trail, get_execution_detail
from .tools.workers import (
    list_workers,
    get_worker_status,
    pause_worker,
    resume_worker,
    get_policy_rules
)
from .tools.integrations import (
    list_integrations,
    get_integration_status,
    trigger_sync
)
from .tools.api_tools import score_fraud, reconcile_datasets, extract_contract_data
from .tools.analytics import get_execution_stats, get_hours_saved

app = Server("clendan")

# Register all tools
app.tool()(parse_invoice)
app.tool()(run_invoice_worker)
app.tool()(score_fraud)
app.tool()(reconcile_datasets)
app.tool()(extract_contract_data)
app.tool()(get_pending_approvals)
app.tool()(approve_execution)
app.tool()(reject_execution)
app.tool()(get_approval_detail)
app.tool()(get_audit_trail)
app.tool()(get_execution_detail)
app.tool()(list_workers)
app.tool()(get_worker_status)
app.tool()(pause_worker)
app.tool()(resume_worker)
app.tool()(get_policy_rules)
app.tool()(list_integrations)
app.tool()(get_integration_status)
app.tool()(trigger_sync)
app.tool()(get_execution_stats)
app.tool()(get_hours_saved)

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
```

---

## auth.py Structure

```python
import os
import httpx
from functools import lru_cache

CLENDAN_API_BASE = os.getenv("CLENDAN_API_BASE", "https://api.clendan.com")
CLENDAN_API_KEY = os.getenv("CLENDAN_API_KEY")

def get_headers() -> dict:
    if not CLENDAN_API_KEY:
        raise ValueError(
            "CLENDAN_API_KEY environment variable is not set. "
            "Get your API key from https://app.clendan.com/dashboard/developer-api"
        )
    return {
        "Authorization": f"Bearer {CLENDAN_API_KEY}",
        "Content-Type": "application/json"
    }

async def api_get(path: str, params: dict = None) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{CLENDAN_API_BASE}{path}",
            headers=get_headers(),
            params=params,
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()

async def api_post(path: str, data: dict = None, files: dict = None) -> dict:
    async with httpx.AsyncClient() as client:
        if files:
            response = await client.post(
                f"{CLENDAN_API_BASE}{path}",
                headers={"Authorization": f"Bearer {CLENDAN_API_KEY}"},
                files=files,
                timeout=60.0
            )
        else:
            response = await client.post(
                f"{CLENDAN_API_BASE}{path}",
                headers=get_headers(),
                json=data,
                timeout=30.0
            )
        response.raise_for_status()
        return response.json()
```

---

## How to Connect (for users)

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "clendan": {
      "command": "uvx",
      "args": ["clendan-mcp"],
      "env": {
        "CLENDAN_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

### Claude Code

```bash
claude mcp add clendan \
  --command uvx \
  --args clendan-mcp \
  --env CLENDAN_API_KEY=your_api_key_here
```

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `CLENDAN_API_KEY` | Yes | Your Clendan API key |
| `CLENDAN_API_BASE` | No | Override API base URL (default: https://api.clendan.com) |

---

## Publishing to PyPI

Package name: `clendan-mcp`

```
pyproject.toml
└── [project]
    name = "clendan-mcp"
    version = "0.1.0"
    description = "MCP server for Clendan AI Financial Agent OS"
    [project.scripts]
    clendan-mcp = "clendan_mcp.server:main"
```

Publish:
```bash
pip install build twine
python -m build
twine upload dist/*
```

After publishing, users can run with `uvx clendan-mcp` — no install required.

---

## Listing on MCP Marketplaces

After publishing to PyPI:

1. **mcpmarket.com** — submit via their listing form
2. **Anthropic MCP directory** — submit via GitHub PR to modelcontextprotocol/servers
3. **Glama.ai** — submit to their MCP registry
4. **Add to Clendan docs** — add MCP setup section to docs.clendan.com

---

## Build Rules

- Every tool must have a clear, accurate docstring — this is what Claude reads
  to decide which tool to use. Vague docstrings = wrong tool calls.
- Every tool must handle API errors gracefully — return structured error
  messages, never raise unhandled exceptions
- Every tool that modifies data (approve, reject, pause, resume) must
  require explicit confirmation in its docstring
- No tool should expose raw API error messages — map to user-friendly strings
- File upload tools (parse_invoice, extract_contract) must validate file
  exists and is the correct type before calling the API
- All tools are async — never use synchronous HTTP calls

---

## Testing the MCP

```bash
# Install MCP inspector
npx @modelcontextprotocol/inspector

# Run the server locally
CLENDAN_API_KEY=your_key python -m clendan_mcp.server

# Connect inspector to stdio
# Test each tool manually before publishing
```

---

## Phase Dependency

Do NOT build this until:
- [ ] Invoice Parser API live and stable
- [ ] Invoice Processing Worker wired end to end
- [ ] Clerk auth working
- [ ] At least one integration (QuickBooks or Xero) connected
- [ ] API keys can be generated from the dashboard

Building the MCP before the API is stable means the tools will be
wrong and will need rewriting. Build the API first, wrap it second.
