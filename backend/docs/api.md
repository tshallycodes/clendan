# Clendan API Reference

## Base URL

```text
https://api-production-0d35.up.railway.app/v1
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

Two authentication schemes are used depending on the endpoint type:

| Endpoint type | Header |
| --- | --- |
| Dashboard (internal) | `Authorization: Bearer <clerk-jwt>` |
| External API (agent execution) | `Authorization: ck_live_...` |

Generate API keys from the Developer page. Keys are shown only once on creation — copy immediately. To revoke, use the Revoke button in the Developer page.

Rate limits (per API key, sliding 60s window):

| Endpoint | Limit |
| --- | --- |
| `POST /v1/execute`, `GET /v1/execute/*` | 60 req/min |
| `/v1/parse/*` | 20 req/min |
| All other `/v1/*` | 200 req/min |

Exceeded limits return `429` with a `Retry-After` header.

## Agent Execution Endpoints

All agent execution endpoints authenticate with `Authorization: ck_live_...`.

### POST /v1/execute

Trigger any deployed tool. Returns immediately with an `execution_id` — poll the result endpoint to get the outcome.

Required headers: `Authorization: ck_live_...`, `Idempotency-Key: <uuid>`, `Content-Type: application/json`

```bash
curl -X POST https://api-production-0d35.up.railway.app/v1/execute \
  -H "Authorization: ck_live_..." \
  -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{"tool": "reconciliation", "payload": {}}'
```

Response:

```json
{ "execution_id": "...", "status": "queued", "decision": "pending", "idempotent": false }
```

Available tool types: `reconciliation`, `document_intelligence`, `spend_control`, `ar_collections`, `risk_compliance`, `treasury_cash`, `revenue_recognition`, `credit_underwriting`, `tax_compliance`, `financial_reporting`, `payment_run`, `budgeting`

### GET /v1/execute/{execution_id}

Poll for the result of a queued execution.

Required headers: `Authorization: ck_live_...`

```bash
curl https://api-production-0d35.up.railway.app/v1/execute/<execution_id> \
  -H "Authorization: ck_live_..."
```

Response fields: `status`, `decision`, `confidence`, `reasoning_trace`, `duration_ms`, `error`

### GET /v1/execute/tools

List all active deployed tools for the tenant.

Required headers: `Authorization: ck_live_...`

```bash
curl https://api-production-0d35.up.railway.app/v1/execute/tools \
  -H "Authorization: ck_live_..."
```

### GET /v1/execute/approvals

List all pending approvals awaiting a human decision.

Required headers: `Authorization: ck_live_...`

```bash
curl https://api-production-0d35.up.railway.app/v1/execute/approvals \
  -H "Authorization: ck_live_..."
```

### POST /v1/execute/approvals/{id}/approve

Approve a pending agent action.

Required headers: `Authorization: ck_live_...`, `Idempotency-Key: <uuid>`

```bash
curl -X POST https://api-production-0d35.up.railway.app/v1/execute/approvals/<id>/approve \
  -H "Authorization: ck_live_..." \
  -H "Idempotency-Key: $(uuidgen)"
```

### POST /v1/execute/approvals/{id}/reject

Reject a pending agent action.

Required headers: `Authorization: ck_live_...`, `Idempotency-Key: <uuid>`

```bash
curl -X POST https://api-production-0d35.up.railway.app/v1/execute/approvals/<id>/reject \
  -H "Authorization: ck_live_..." \
  -H "Idempotency-Key: $(uuidgen)"
```

### GET /v1/execute/audit

Query the immutable audit log. Supports `limit` and `offset` query parameters (default: limit=20, offset=0).

Required headers: `Authorization: ck_live_...`

```bash
curl "https://api-production-0d35.up.railway.app/v1/execute/audit?limit=20&offset=0" \
  -H "Authorization: ck_live_..."
```

### GET /v1/execute/transactions

List synced bank transactions. Supports `limit` and `offset` query parameters.

Required headers: `Authorization: ck_live_...`

```bash
curl "https://api-production-0d35.up.railway.app/v1/execute/transactions?limit=20&offset=0" \
  -H "Authorization: ck_live_..."
```

## Idempotency

All POST requests require an `Idempotency-Key` header. Use a UUID generated at the point of the call. Sending the same key again returns the existing result without re-executing.

```python
import uuid
idempotency_key = str(uuid.uuid4())  # generate fresh per intended operation
```

## Webhook Events

| Event | Description |
| --- | --- |
| `tool.executed` | Tool completed execution |
| `tool.approval_required` | Human approval needed |
| `tool.policy_blocked` | Policy engine blocked action |
| `reconciliation.complete` | Reconciliation run finished |
| `invoice.processed` | Invoice classified and routed |
| `transaction.synced` | New transactions ingested |
| `audit.written` | Audit log entry created |

## Python Example

```python
import uuid, requests

API_KEY = "ck_live_..."
BASE = "https://api-production-0d35.up.railway.app/v1"

resp = requests.post(
    f"{BASE}/execute",
    headers={
        "Authorization": API_KEY,
        "Idempotency-Key": str(uuid.uuid4()),
        "Content-Type": "application/json",
    },
    json={"tool": "reconciliation", "payload": {}},
)
data = resp.json()["data"]
print(data["execution_id"], data["status"])  # "queued"
```

## TypeScript Example

```typescript
const API_KEY = "ck_live_..."
const BASE = "https://api-production-0d35.up.railway.app/v1"

const res = await fetch(`${BASE}/execute`, {
  method: "POST",
  headers: {
    "Authorization": API_KEY,
    "Idempotency-Key": crypto.randomUUID(),
    "Content-Type": "application/json",
  },
  body: JSON.stringify({ tool: "reconciliation", payload: {} }),
})

const { data } = await res.json()
console.log(data.execution_id, data.status) // "queued"
```
