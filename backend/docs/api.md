# Clendan API Reference

## Base URL

```
https://api.clendan.com/v1
```

All endpoints are versioned under `/v1`. Every response has this shape:

```json
{
  "data":      { ... },
  "error":     null,
  "trace_id":  "4c3879c5-7d59-...",
  "timestamp": "2026-06-04T21:18:12.982Z"
}
```

## Authentication

Dashboard endpoints use a short-lived Clerk JWT passed as `Authorization: Bearer <token>`.

Agent execution endpoints use `X-Tenant-ID` (your tenant ID) paired with `Idempotency-Key` (unique UUID per operation).

Financial write endpoints require `Idempotency-Key` — the same key safely retries and returns the existing result.

Rate limit: 120 requests per minute.

## Endpoints

### POST /v1/onboarding
Create your tenant and user on first sign-in. Safe to call multiple times — idempotent.
Required headers: `Authorization: Bearer <clerk-token>`

### GET /v1/dashboard/stats
Returns execution counts, pending approvals, active tools, invoices processed, and transactions synced.
Required headers: `Authorization: Bearer <clerk-token>`

### GET /v1/dashboard/executions?limit=20&offset=0
Paginated list of agent executions for your tenant, newest first.
Required headers: `Authorization: Bearer <clerk-token>`

### GET /v1/dashboard/approvals
All pending human-approval requests awaiting a decision.
Required headers: `Authorization: Bearer <clerk-token>`

### GET /v1/dashboard/audit
Immutable audit trail — append-only log of every agent action.
Required headers: `Authorization: Bearer <clerk-token>`

### POST /v1/agents/{tool_id}/run
Enqueue a document for processing by a specific tool. Returns immediately with execution_id.
Required headers: `X-Tenant-ID`, `Idempotency-Key`

```bash
FILE_B64=$(base64 -w0 invoice.pdf)

curl -X POST https://api.clendan.com/v1/agents/<tool_id>/run \
  -H "X-Tenant-ID: <your-tenant-id>" \
  -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  -d "{\"file_bytes_b64\": \"$FILE_B64\", \"content_type\": \"application/pdf\"}"
```

### POST /v1/approvals/{approval_id}/respond
Approve or reject a pending action. Enforces expiry TTL — stale approvals rejected with 410.
Required headers: `X-Tenant-ID`

```json
{ "action": "approve", "responder_id": "<your-user-id>" }
{ "action": "reject",  "responder_id": "<your-user-id>" }
```

### POST /v1/execute
Run any deployed tool directly.

### GET /v1/tools
List all deployed tools for your tenant.

### GET /v1/approvals
List all pending approvals.

### POST /v1/approvals/{id}/approve
Approve an agent action.

### POST /v1/approvals/{id}/reject
Reject an agent action.

### GET /v1/audit
Query the immutable audit log.

### GET /v1/transactions
List synced bank transactions.

### POST /v1/webhooks
Register a webhook endpoint to receive real-time events.

## Webhook Events

| Event | Description |
|---|---|
| `tool.executed` | Tool completed execution |
| `tool.approval_required` | Human approval needed |
| `tool.policy_blocked` | Policy engine blocked action |
| `reconciliation.complete` | Reconciliation run finished |
| `invoice.processed` | Invoice classified and routed |
| `transaction.synced` | New transactions ingested |
| `audit.written` | Audit log entry created |

## API Keys

Generate API keys in the Developer page. Keys are prefixed `ck_live_` for production. Keys are shown only once — copy them immediately. To revoke, use the Revoke button in the Developer page.

Pass keys as the Authorization header: `Authorization: ck_live_...`

## Python Example

```python
import base64, uuid, httpx

BASE = "https://api.clendan.com/v1"
TENANT_ID = "<your-tenant-id>"
TOOL_ID = "<your-tool-id>"

with open("invoice.pdf", "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

resp = httpx.post(
    f"{BASE}/agents/{TOOL_ID}/run",
    headers={
        "X-Tenant-ID":     TENANT_ID,
        "Idempotency-Key": str(uuid.uuid4()),
    },
    json={"file_bytes_b64": b64, "content_type": "application/pdf"},
)
print(resp.json()["data"])  # {"execution_id": "...", "status": "queued"}
```

## TypeScript Example

```typescript
const BASE = "https://api.clendan.com/v1"
const TENANT_ID = "<your-tenant-id>"
const TOOL_ID = "<your-tool-id>"

const fileBytes = await fs.readFile("invoice.pdf")
const b64 = fileBytes.toString("base64")

const res = await fetch(`${BASE}/agents/${TOOL_ID}/run`, {
  method: "POST",
  headers: {
    "X-Tenant-ID":     TENANT_ID,
    "Idempotency-Key": crypto.randomUUID(),
    "Content-Type":    "application/json",
  },
  body: JSON.stringify({ file_bytes_b64: b64, content_type: "application/pdf" }),
})

const { data } = await res.json()
console.log(data.execution_id, data.status) // "queued"
```
