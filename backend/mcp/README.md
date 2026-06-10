# Clendan MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that exposes
Clendan's AI Financial Agent OS as tools any MCP client can call.

Connect Claude Desktop, Claude Code, or any MCP-compatible client to your
Clendan account and interact with it conversationally — no REST API code needed.

---

## Quick Start

### Claude Desktop

Add to your `claude_desktop_config.json`:

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

| Variable | Required | Default | Description |
|---|---|---|---|
| `CLENDAN_API_KEY` | **Yes** | — | Your Clendan API key. Get it at [app.clendan.com/dashboard/developer-api](https://app.clendan.com/dashboard/developer-api) |
| `CLENDAN_API_BASE` | No | `https://api.clendan.com` | Override the API base URL (useful for self-hosted or staging) |

---

## Available Tools

### Financial Operations

| Tool | Description |
|---|---|
| `parse_invoice` | Parse a PDF/PNG/JPG invoice and extract structured data |
| `run_invoice_worker` | Run the Invoice Processing Worker on parsed invoice data |
| `score_fraud` | Score a transaction for fraud risk |
| `reconcile_datasets` | Reconcile two financial datasets |
| `extract_contract_data` | Extract structured data from a contract PDF |

### Approval Queue

| Tool | Description |
|---|---|
| `get_pending_approvals` | List all executions waiting for human approval |
| `approve_execution` | Approve a pending execution |
| `reject_execution` | Reject a pending execution (reason required) |
| `get_approval_detail` | Get full reasoning trace for a pending approval |

### Audit Trail

| Tool | Description |
|---|---|
| `get_audit_trail` | Query the immutable audit trail (filter by type, status, date) |
| `get_execution_detail` | Get complete detail of an execution by trace ID |

### Workers

| Tool | Description |
|---|---|
| `list_workers` | List all deployed workers and their status |
| `get_worker_status` | Get detailed status of a specific worker |
| `pause_worker` | Pause a running worker |
| `resume_worker` | Resume a paused worker |
| `get_policy_rules` | Get policy rules and thresholds for a worker |

### Integrations

| Tool | Description |
|---|---|
| `list_integrations` | List all integrations and connection status |
| `get_integration_status` | Get detailed status of a specific integration |
| `trigger_sync` | Manually trigger a data resync |

### Analytics

| Tool | Description |
|---|---|
| `get_execution_stats` | Get execution statistics for a period (1d/7d/30d/90d) |
| `get_hours_saved` | Calculate hours saved by workers over a period |

---

## Example Conversations

```
You: What invoices are waiting for my approval?
Claude: [calls get_pending_approvals] You have 3 pending approvals...

You: Show me the reasoning for the Acme Corp invoice
Claude: [calls get_approval_detail] The worker escalated because the amount (£45,200)
        exceeds your auto-approval threshold of £25,000...

You: Approve it — it looks fine
Claude: [calls approve_execution] Done. The invoice has been approved and will
        be posted to QuickBooks automatically.

You: How much time has Clendan saved us this month?
Claude: [calls get_hours_saved] Over the last 30 days, your workers processed
        847 tasks and saved approximately 127 hours of manual work...
```

---

## Running Locally (Development)

```bash
cd backend/mcp
pip install -e ".[dev]"

# Run the server (stdio transport)
CLENDAN_API_KEY=your_key python -m clendan_mcp.server

# Test with the MCP inspector
npx @modelcontextprotocol/inspector
```

---

## Publishing to PyPI

```bash
cd backend/mcp
pip install build twine
python -m build
twine upload dist/*
```

After publishing, users can run with `uvx clendan-mcp` — no install required.

---

## MCP Marketplace Listings

After publishing to PyPI, submit to:
1. **mcpmarket.com** — submit via their listing form
2. **Anthropic MCP directory** — PR to `modelcontextprotocol/servers`
3. **Glama.ai** — submit to their MCP registry
