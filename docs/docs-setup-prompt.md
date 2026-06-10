# Clendan — Documentation (Mintlify)
# Complete setup + all content

---

## PART 1 — MINTLIFY SETUP

### Step 1 — Create Mintlify Account
1. Go to https://mintlify.com
2. Sign up with your GitHub account
3. Click "New Docs"
4. Name: "Clendan Docs"
5. Connect to your GitHub repo: `your-username/clendan`
6. Set docs directory: `/docs` (Mintlify will create this folder)

### Step 2 — Create docs/ folder in repo root

```
clendan/
└── docs/
    ├── mint.json              # Mintlify config — controls nav, branding, structure
    ├── favicon.svg            # Clendan logo mark
    ├── logo/
    │   ├── light.svg          # Logo for light mode
    │   └── dark.svg           # Logo for dark mode
    ├── introduction.mdx
    ├── quickstart.mdx
    ├── authentication.mdx
    ├── api-reference/
    │   ├── overview.mdx
    │   ├── invoice-parser.mdx
    │   ├── receipt-ocr.mdx
    │   ├── reconciliation.mdx
    │   ├── fraud-signal.mdx
    │   └── contract-extraction.mdx
    ├── workers/
    │   ├── overview.mdx
    │   ├── invoice-processing.mdx
    │   ├── accountant.mdx
    │   ├── reconciliation.mdx
    │   ├── expense-control.mdx
    │   ├── collections.mdx
    │   ├── fraud-detection.mdx
    │   ├── treasury.mdx
    │   └── revenue-recognition.mdx
    ├── integrations/
    │   ├── overview.mdx
    │   ├── quickbooks.mdx
    │   ├── xero.mdx
    │   ├── plaid.mdx
    │   ├── stripe.mdx
    │   ├── gocardless.mdx
    │   └── gmail.mdx
    ├── platform/
    │   ├── organisations.mdx
    │   ├── team-roles.mdx
    │   ├── policy-engine.mdx
    │   ├── audit-trail.mdx
    │   ├── webhooks.mdx
    │   └── api-keys.mdx
    └── guides/
        ├── process-first-invoice.mdx
        ├── connect-xero.mdx
        ├── set-approval-thresholds.mdx
        ├── invite-your-team.mdx
        └── month-end-close.mdx
```

### Step 3 — mint.json (Mintlify config)

Create `docs/mint.json`:

```json
{
  "name": "Clendan",
  "logo": {
    "dark": "/logo/dark.svg",
    "light": "/logo/light.svg"
  },
  "favicon": "/favicon.svg",
  "colors": {
    "primary": "#00C853",
    "light": "#00E676",
    "dark": "#00a844",
    "background": {
      "dark": "#0a0a0f"
    }
  },
  "topbarLinks": [
    {
      "name": "Dashboard",
      "url": "https://app.clendan.com/dashboard"
    }
  ],
  "topbarCtaButton": {
    "name": "Get Started",
    "url": "https://app.clendan.com/sign-up"
  },
  "tabs": [
    {
      "name": "API Reference",
      "url": "api-reference"
    },
    {
      "name": "Workers",
      "url": "workers"
    },
    {
      "name": "Integrations",
      "url": "integrations"
    }
  ],
  "anchors": [
    {
      "name": "Changelog",
      "icon": "list",
      "url": "https://clendan.com/changelog"
    },
    {
      "name": "Status",
      "icon": "signal",
      "url": "https://status.clendan.com"
    },
    {
      "name": "Support",
      "icon": "envelope",
      "url": "mailto:support@clendan.com"
    }
  ],
  "navigation": [
    {
      "group": "Getting Started",
      "pages": [
        "introduction",
        "quickstart",
        "authentication"
      ]
    },
    {
      "group": "API Reference",
      "pages": [
        "api-reference/overview",
        "api-reference/invoice-parser",
        "api-reference/receipt-ocr",
        "api-reference/reconciliation",
        "api-reference/fraud-signal",
        "api-reference/contract-extraction"
      ]
    },
    {
      "group": "AI Workers",
      "pages": [
        "workers/overview",
        "workers/invoice-processing",
        "workers/accountant",
        "workers/reconciliation",
        "workers/expense-control",
        "workers/collections",
        "workers/fraud-detection",
        "workers/treasury",
        "workers/revenue-recognition"
      ]
    },
    {
      "group": "Integrations",
      "pages": [
        "integrations/overview",
        "integrations/quickbooks",
        "integrations/xero",
        "integrations/plaid",
        "integrations/stripe",
        "integrations/gocardless",
        "integrations/gmail"
      ]
    },
    {
      "group": "Platform",
      "pages": [
        "platform/organisations",
        "platform/team-roles",
        "platform/policy-engine",
        "platform/audit-trail",
        "platform/webhooks",
        "platform/api-keys"
      ]
    },
    {
      "group": "Guides",
      "pages": [
        "guides/process-first-invoice",
        "guides/connect-xero",
        "guides/set-approval-thresholds",
        "guides/invite-your-team",
        "guides/month-end-close"
      ]
    }
  ],
  "footerSocials": {
    "twitter": "https://twitter.com/clendan",
    "github": "https://github.com/clendan",
    "linkedin": "https://linkedin.com/company/clendan"
  }
}
```

### Step 4 — Domain Setup
1. Go to your domain registrar (Namecheap, GoDaddy, Cloudflare etc.)
2. Add a CNAME record:
   - Name: `docs`
   - Value: `mintlify.app` (Mintlify will give you the exact value)
3. In Mintlify dashboard → Settings → Custom Domain
4. Enter: `docs.clendan.com`
5. Wait for DNS propagation (up to 48 hours, usually faster)

---

## PART 2 — DOCUMENTATION CONTENT

Write each file exactly as shown below.

---

### docs/introduction.mdx

```mdx
---
title: Introduction
description: Clendan is an AI Financial Agent OS — execution infrastructure for autonomous finance operations.
---

# Welcome to Clendan

Clendan is an API platform where companies deploy **AI financial workers** that connect to their financial systems, execute tasks autonomously, enforce policy rules, and produce full audit trails for every action taken.

<CardGroup cols={2}>
  <Card title="Quickstart" icon="rocket" href="/quickstart">
    Deploy your first AI worker in under 10 minutes
  </Card>
  <Card title="API Reference" icon="code" href="/api-reference/overview">
    Explore the full API — 5 standalone tools, ready to integrate
  </Card>
  <Card title="AI Workers" icon="robot" href="/workers/overview">
    10 specialised workers covering every finance function
  </Card>
  <Card title="Integrations" icon="plug" href="/integrations/overview">
    Connect Xero, QuickBooks, Plaid, Stripe, and more
  </Card>
</CardGroup>

## What Clendan Is

Clendan is **execution infrastructure** — not a dashboard, not a chatbot, not an analytics tool.

When a worker runs, it does not suggest what to do. It executes: parsing invoices, writing bills to your ERP, scheduling payments, flagging fraud, reconciling accounts. Every action is logged to an immutable audit trail with full reasoning traces.

## Architecture

Clendan uses a **master-subagent model**:

- The **Financial Orchestrator** is the master agent. It receives all financial events, classifies them, and routes them to the right worker.
- Each **AI Worker** is a specialised sub-agent — it has a defined role, tools it can call, and policies it must enforce.
- Workers never call each other directly. All coordination flows through the Orchestrator.

## Not Sure Where to Start?

<Steps>
  <Step title="Read the Quickstart">
    Connect your first integration and process a real invoice end to end.
  </Step>
  <Step title="Explore the Workers">
    See what each AI worker does and which phase it's available in.
  </Step>
  <Step title="Try the API Tools">
    Use the standalone APIs directly from your own system — no platform required.
  </Step>
</Steps>
```

---

### docs/quickstart.mdx

```mdx
---
title: Quickstart
description: Deploy your first AI worker and process a real invoice in under 10 minutes.
---

# Quickstart

This guide walks you through:
1. Creating your Clendan account
2. Connecting QuickBooks or Xero
3. Deploying the Invoice Processing Worker
4. Processing your first invoice

## Step 1 — Create Your Account

Go to [app.clendan.com/sign-up](https://app.clendan.com/sign-up) and create an account.

After signup you'll be taken through onboarding:
- Enter your company details
- Invite your finance team (optional)
- Connect your first integration
- Deploy your first worker

## Step 2 — Get Your API Key

1. Go to **Dashboard → Developer API**
2. Click **Create new API key**
3. Name it (e.g. "My first key")
4. Copy the key — it will only be shown once

<Warning>
Store your API key securely. Never commit it to version control or expose it in client-side code.
</Warning>

All API requests require the following header:
```
Authorization: Bearer YOUR_API_KEY
```

## Step 3 — Parse Your First Invoice

Upload an invoice PDF and get back structured JSON in under 2 seconds.

<CodeGroup>
```python Python
import requests

with open("invoice.pdf", "rb") as f:
    response = requests.post(
        "https://api.clendan.com/v1/parse/invoice",
        headers={"Authorization": "Bearer YOUR_API_KEY"},
        files={"file": f}
    )

data = response.json()
print(data["data"]["vendor"])        # "Acme Supplies Ltd"
print(data["data"]["total_amount"])  # 1240.00
print(data["data"]["confidence"])    # 0.97
```

```javascript Node.js
const FormData = require('form-data');
const fs = require('fs');
const fetch = require('node-fetch');

const form = new FormData();
form.append('file', fs.createReadStream('invoice.pdf'));

const response = await fetch('https://api.clendan.com/v1/parse/invoice', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_API_KEY',
    ...form.getHeaders()
  },
  body: form
});

const data = await response.json();
console.log(data.data.vendor);       // "Acme Supplies Ltd"
console.log(data.data.total_amount); // 1240.00
```

```bash cURL
curl -X POST https://api.clendan.com/v1/parse/invoice \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@invoice.pdf"
```
</CodeGroup>

## Step 4 — Connect an Integration

Connect QuickBooks or Xero from your dashboard so the Invoice Processing Worker can write bills directly to your accounting software.

1. Go to **Dashboard → Integrations**
2. Click **Connect** on QuickBooks or Xero
3. Authenticate with your accounting software
4. Wait for the initial sync to complete (usually under 2 minutes)

## Step 5 — Deploy the Invoice Processing Worker

1. Go to **Dashboard → Workers**
2. Click **Deploy** on the Invoice Processing Worker
3. Set your autonomy level:
   - **Auto** — processes invoices under your threshold without approval
   - **Approve** — always asks before acting
   - **Suggest** — recommends actions, you execute manually
4. Set your approval threshold (e.g. auto-approve under £500)
5. Click **Deploy Worker**

Your worker is now live. Any invoice that arrives — via email, upload, or API — will be processed automatically.

## Next Steps

<CardGroup cols={2}>
  <Card title="Invite Your Team" icon="users" href="/guides/invite-your-team">
    Add your finance team so they can review approvals
  </Card>
  <Card title="Set Approval Thresholds" icon="sliders" href="/guides/set-approval-thresholds">
    Configure exactly when workers act autonomously
  </Card>
  <Card title="Connect More Integrations" icon="plug" href="/integrations/overview">
    Connect Plaid, Stripe, and more
  </Card>
  <Card title="Explore the API" icon="code" href="/api-reference/overview">
    Call Clendan APIs directly from your own system
  </Card>
</CardGroup>
```

---

### docs/authentication.mdx

```mdx
---
title: Authentication
description: How to authenticate with the Clendan API.
---

# Authentication

All Clendan API requests are authenticated using API keys.

## Getting Your API Key

1. Go to **Dashboard → Developer API**
2. Click **Create new API key**
3. Give it a name and set permissions (read-only or read-write)
4. Copy the key immediately — it will not be shown again

## Using Your API Key

Include your API key in the `Authorization` header of every request:

```
Authorization: Bearer YOUR_API_KEY
```

<CodeGroup>
```python Python
import requests

headers = {"Authorization": "Bearer YOUR_API_KEY"}

response = requests.post(
    "https://api.clendan.com/v1/parse/invoice",
    headers=headers,
    files={"file": open("invoice.pdf", "rb")}
)
```

```javascript Node.js
const response = await fetch('https://api.clendan.com/v1/parse/invoice', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_API_KEY'
  }
});
```

```bash cURL
curl https://api.clendan.com/v1/parse/invoice \
  -H "Authorization: Bearer YOUR_API_KEY"
```
</CodeGroup>

## API Key Permissions

| Permission | Description |
|---|---|
| `read-only` | Can call GET endpoints and retrieve data |
| `read-write` | Can call all endpoints including POST, PATCH, DELETE |
| `admin` | Full access including API key management |

## Idempotency Keys

For write operations, we recommend including an `Idempotency-Key` header.
This ensures that if a request is retried (due to a network error), it will
not be processed twice.

```
Idempotency-Key: a-unique-key-you-generate
```

Keys are valid for 24 hours. Use a UUID or a hash of the request content.

## Response Format

Every API response follows the same structure:

```json
{
  "data": { },
  "error": null,
  "trace_id": "trace-a1b2c3d4",
  "timestamp": "2026-05-20T09:14:52Z"
}
```

On error:

```json
{
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invoice file is required",
    "details": {}
  },
  "trace_id": "trace-a1b2c3d4",
  "timestamp": "2026-05-20T09:14:52Z"
}
```

## Error Codes

| Code | HTTP Status | Description |
|---|---|---|
| `UNAUTHORIZED` | 401 | Missing or invalid API key |
| `FORBIDDEN` | 403 | Valid key but insufficient permissions |
| `NOT_FOUND` | 404 | Resource does not exist |
| `VALIDATION_ERROR` | 422 | Invalid request body or parameters |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Something went wrong on our end |

## Rate Limits

| Plan | Requests per minute |
|---|---|
| Starter | 60 |
| Growth | 300 |
| Enterprise | Custom |

Rate limit headers are included in every response:
```
X-RateLimit-Limit: 300
X-RateLimit-Remaining: 299
X-RateLimit-Reset: 1716200000
```
```

---

### docs/api-reference/overview.mdx

```mdx
---
title: API Overview
description: Clendan's 5 standalone API tools — use them inside the platform or from your own systems.
---

# API Reference

Clendan provides 5 standalone API tools. Each one solves a specific financial
data problem. Use them inside the Clendan platform or call them directly
from your own systems.

## Base URL

```
https://api.clendan.com
```

## Available APIs

<CardGroup cols={2}>
  <Card title="Invoice Parser" icon="file-invoice" href="/api-reference/invoice-parser">
    `POST /v1/parse/invoice` — extract structured data from any invoice format
  </Card>
  <Card title="Receipt OCR + Policy" icon="receipt" href="/api-reference/receipt-ocr">
    `POST /v1/parse/receipt` — extract receipt data and validate against policy
  </Card>
  <Card title="Document Reconciliation" icon="scale-balanced" href="/api-reference/reconciliation">
    `POST /v1/reconcile` — match two financial datasets and flag mismatches
  </Card>
  <Card title="Fraud Signal" icon="shield-halved" href="/api-reference/fraud-signal">
    `POST /v1/fraud/score` — score transaction risk with full reasoning
  </Card>
  <Card title="Contract Extraction" icon="file-contract" href="/api-reference/contract-extraction">
    `POST /v1/parse/contract` — extract structured data from contract PDFs
  </Card>
</CardGroup>

## Common Headers

| Header | Required | Description |
|---|---|---|
| `Authorization` | Yes | `Bearer YOUR_API_KEY` |
| `Idempotency-Key` | Recommended | Unique key to prevent duplicate processing |
| `Content-Type` | Auto | Set automatically for multipart/form-data uploads |
```

---

### docs/api-reference/invoice-parser.mdx

```mdx
---
title: Invoice Parser API
description: Extract structured data from any invoice — PDF, PNG, JPG, or TIFF.
---

# Invoice Parser API

Extract structured JSON from any invoice document. Supports PDF, PNG, JPG,
and TIFF. Returns vendor details, line items, amounts, dates, and a
confidence score. No templates. No configuration.

## Endpoint

```
POST /v1/parse/invoice
```

## Request

**Content-Type:** `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | File | Yes | Invoice document (PDF, PNG, JPG, TIFF, max 10MB) |
| `currency_hint` | String | No | ISO 4217 currency code hint (e.g. "GBP") |

**Headers:**

| Header | Required | Description |
|---|---|---|
| `Authorization` | Yes | `Bearer YOUR_API_KEY` |
| `Idempotency-Key` | Recommended | Unique key for retry safety |

## Response

```json
{
  "data": {
    "vendor": "Acme Supplies Ltd",
    "invoice_number": "INV-2026-0041",
    "invoice_date": "2026-05-01",
    "due_date": "2026-06-15",
    "currency": "GBP",
    "subtotal": 1033.33,
    "vat_amount": 206.67,
    "total_amount": 1240.00,
    "total_amount_minor": 124000,
    "po_number": "PO-2026-0089",
    "line_items": [
      {
        "description": "Cloud infrastructure services",
        "quantity": 1,
        "unit_price": 1033.33,
        "total": 1033.33
      }
    ],
    "confidence": 0.97,
    "flags": []
  },
  "error": null,
  "trace_id": "trace-a1b2c3d4",
  "timestamp": "2026-05-20T09:14:33Z"
}
```

<Note>
`total_amount_minor` is the total in minor currency units (pence for GBP, cents for USD).
Always use this for financial calculations — never `total_amount` which is for display only.
</Note>

## Confidence Score

The `confidence` field (0.0–1.0) indicates extraction reliability:

| Range | Meaning |
|---|---|
| 0.95–1.0 | High confidence — safe to auto-process |
| 0.80–0.94 | Medium confidence — review recommended |
| Below 0.80 | Low confidence — manual review required |

## Flags

The `flags` array contains warnings about the extracted data:

| Flag | Description |
|---|---|
| `DUPLICATE_INVOICE_NUMBER` | This invoice number has been seen before |
| `AMOUNT_MISMATCH` | Line item totals do not match the invoice total |
| `MISSING_PO_NUMBER` | No PO number found on the invoice |
| `UNRECOGNISED_VENDOR` | Vendor not in your approved supplier list |

## Code Examples

<CodeGroup>
```python Python
import requests

with open("invoice.pdf", "rb") as f:
    response = requests.post(
        "https://api.clendan.com/v1/parse/invoice",
        headers={
            "Authorization": "Bearer YOUR_API_KEY",
            "Idempotency-Key": "inv-parse-20260520-001"
        },
        files={"file": ("invoice.pdf", f, "application/pdf")}
    )

result = response.json()

if result["error"]:
    print(f"Error: {result['error']['message']}")
else:
    invoice = result["data"]
    print(f"Vendor: {invoice['vendor']}")
    print(f"Amount: {invoice['currency']} {invoice['total_amount']}")
    print(f"Confidence: {invoice['confidence']}")
    print(f"Flags: {invoice['flags']}")
```

```javascript Node.js
const FormData = require('form-data');
const fs = require('fs');
const fetch = require('node-fetch');

const form = new FormData();
form.append('file', fs.createReadStream('invoice.pdf'), {
  filename: 'invoice.pdf',
  contentType: 'application/pdf'
});

const response = await fetch('https://api.clendan.com/v1/parse/invoice', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_API_KEY',
    'Idempotency-Key': 'inv-parse-20260520-001',
    ...form.getHeaders()
  },
  body: form
});

const result = await response.json();

if (result.error) {
  console.error('Error:', result.error.message);
} else {
  const invoice = result.data;
  console.log('Vendor:', invoice.vendor);
  console.log('Amount:', invoice.currency, invoice.total_amount);
  console.log('Confidence:', invoice.confidence);
}
```

```bash cURL
curl -X POST https://api.clendan.com/v1/parse/invoice \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Idempotency-Key: inv-parse-20260520-001" \
  -F "file=@invoice.pdf;type=application/pdf"
```
</CodeGroup>

## Error Responses

| Code | Description |
|---|---|
| `INVALID_FILE_TYPE` | File must be PDF, PNG, JPG, or TIFF |
| `FILE_TOO_LARGE` | File exceeds 10MB limit |
| `EXTRACTION_FAILED` | Could not extract data from document |
| `LOW_CONFIDENCE` | Confidence below minimum threshold (0.5) |
```

---

### docs/api-reference/fraud-signal.mdx

```mdx
---
title: Fraud Signal API
description: Score transaction risk in real time with full reasoning.
---

# Fraud Signal API

Score any transaction for fraud risk. Returns a risk score, risk level,
detected signals, recommended action, and full reasoning. Designed for
inline use — low latency, no configuration required.

## Endpoint

```
POST /v1/fraud/score
```

## Request

```json
{
  "transaction_id": "txn-001",
  "amount_minor": 124000,
  "currency": "GBP",
  "counterparty": "Acme Supplies Ltd",
  "transaction_type": "invoice_payment",
  "timestamp": "2026-05-20T09:14:00Z",
  "metadata": {
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0"
  }
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `transaction_id` | String | Yes | Your unique transaction ID |
| `amount_minor` | Integer | Yes | Amount in minor currency units |
| `currency` | String | Yes | ISO 4217 currency code |
| `counterparty` | String | Yes | Name of the other party |
| `transaction_type` | String | Yes | Type of transaction |
| `timestamp` | String | Yes | ISO 8601 datetime |
| `metadata` | Object | No | Additional context |

## Response

```json
{
  "data": {
    "transaction_id": "txn-001",
    "risk_score": 0.12,
    "risk_level": "low",
    "action": "allow",
    "signals": [],
    "reasoning": "Transaction amount within normal range for this counterparty. No suspicious patterns detected. Counterparty verified in approved supplier list.",
    "confidence": 0.94
  },
  "error": null,
  "trace_id": "trace-b2c3d4e5",
  "timestamp": "2026-05-20T09:14:01Z"
}
```

## Risk Levels

| Level | Score Range | Recommended Action |
|---|---|---|
| `low` | 0.0–0.29 | Allow |
| `medium` | 0.30–0.59 | Flag for review |
| `high` | 0.60–0.79 | Block and escalate |
| `critical` | 0.80–1.0 | Block immediately |

## Code Examples

<CodeGroup>
```python Python
import requests

response = requests.post(
    "https://api.clendan.com/v1/fraud/score",
    headers={"Authorization": "Bearer YOUR_API_KEY"},
    json={
        "transaction_id": "txn-001",
        "amount_minor": 124000,
        "currency": "GBP",
        "counterparty": "Acme Supplies Ltd",
        "transaction_type": "invoice_payment",
        "timestamp": "2026-05-20T09:14:00Z"
    }
)

result = response.json()
fraud = result["data"]

if fraud["risk_level"] in ["high", "critical"]:
    print(f"BLOCK transaction — risk score: {fraud['risk_score']}")
    print(f"Signals: {fraud['signals']}")
else:
    print(f"ALLOW — risk level: {fraud['risk_level']}")
```

```javascript Node.js
const response = await fetch('https://api.clendan.com/v1/fraud/score', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_API_KEY',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    transaction_id: 'txn-001',
    amount_minor: 124000,
    currency: 'GBP',
    counterparty: 'Acme Supplies Ltd',
    transaction_type: 'invoice_payment',
    timestamp: new Date().toISOString()
  })
});

const result = await response.json();
const { risk_level, risk_score, action } = result.data;

if (['high', 'critical'].includes(risk_level)) {
  console.log(`BLOCK — score: ${risk_score}`);
} else {
  console.log(`ALLOW — level: ${risk_level}`);
}
```

```bash cURL
curl -X POST https://api.clendan.com/v1/fraud/score \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "txn-001",
    "amount_minor": 124000,
    "currency": "GBP",
    "counterparty": "Acme Supplies Ltd",
    "transaction_type": "invoice_payment",
    "timestamp": "2026-05-20T09:14:00Z"
  }'
```
</CodeGroup>
```

---

### docs/workers/overview.mdx

```mdx
---
title: AI Workers Overview
description: Clendan's 10 specialised AI workers — each one a sub-agent with a defined role.
---

# AI Workers

Clendan workers are specialised AI sub-agents. Each worker has a defined role,
a set of tools it can call, and policy rules it must enforce. Workers are
deployed per organisation and configured independently.

## Architecture

Clendan uses a master-subagent model:

```
Financial Orchestrator (Master Agent)
├── Receives all financial events
├── Classifies the event type
├── Routes to the correct worker
└── Workers execute as sub-agents
    ├── Invoice Processing Worker
    ├── AI Accountant Worker
    ├── Reconciliation Worker
    └── ... (all others)
```

Workers never call each other directly. All coordination flows through
the Financial Orchestrator.

## Autonomy Levels

Every worker is configured with one of three autonomy levels:

| Level | Behaviour |
|---|---|
| **Auto** | Executes actions autonomously within your policy thresholds |
| **Approve** | Always requests human approval before executing |
| **Suggest** | Recommends actions but never executes — you confirm manually |

## Available Workers

| Worker | Phase | Purpose |
|---|---|---|
| Invoice Processing | MVP | Automate invoice lifecycle end to end |
| AI Accountant | MVP | Categorise transactions, update ledger |
| Reconciliation | V2 | Match accounts across multiple systems |
| Expense Control | V2 | Enforce spending policy on expense claims |
| Collections | V2 | Recover overdue invoices automatically |
| Fraud Detection | V2 | Monitor transactions for suspicious activity |
| Treasury | V2 | Optimise cash flow and liquidity |
| Revenue Recognition | V2 | Apply ASC 606 / IFRS 15 automatically |
| Credit Underwriting | V3 | Evaluate and decide on credit applications |
| Compliance | V3 | Monitor for regulatory violations |

## Policy Engine

Every worker output passes through the policy engine before any action
is taken. The policy engine is deterministic — same input always produces
the same decision.

Policies are configured per worker per organisation:
- Approval thresholds (amount ranges)
- Verified supplier/vendor lists
- Currency allow-lists
- Restricted fields
- Human override triggers

See [Policy Engine](/platform/policy-engine) for full configuration reference.

## Audit Trail

Every action taken by every worker is written to the immutable audit trail
before the response is returned. If the audit write fails, the operation fails.

Each audit entry contains:
- Worker name and version
- Full input data
- Policy evaluation results (each rule, pass/fail)
- Decision and confidence score
- Actions executed
- Reasoning trace
- Duration

See [Audit Trail](/platform/audit-trail) for details.
```

---

### docs/platform/policy-engine.mdx

```mdx
---
title: Policy Engine
description: Configure exactly when workers act autonomously and when they escalate.
---

# Policy Engine

The policy engine evaluates every worker output before any action is taken.
It is deterministic — the same input always produces the same decision.
It cannot be bypassed.

## How It Works

```
Worker produces output
        ↓
Policy engine evaluates all rules
        ↓
    ┌───────────┬──────────────┬──────────┐
    ▼           ▼              ▼          
  PASS      APPROVE        BLOCK
  Auto-     Request        Hold action
  execute   approval       escalate
```

## Configuring Policies

Policies are configured per worker in **Dashboard → Workers → Configure**.

### Amount Thresholds

The most common policy — controls when workers act autonomously vs escalate:

| Range | Action |
|---|---|
| Under threshold 1 | Auto-execute |
| Threshold 1 to threshold 2 | Request approval |
| Above threshold 2 | Block and escalate |

**Example:**
- Auto-approve: under £500
- Approval required: £500 – £5,000
- Block: above £5,000

### Supplier Verification

Restrict workers to only process invoices from approved vendors:

- **Verified list only** — only process invoices from vendors in your approved list
- **Flag unrecognised** — process but flag invoices from unrecognised vendors
- **Allow all** — no vendor restriction

### Currency Rules

Restrict which currencies a worker will process:
- Allow specific currencies only (e.g. GBP, USD, EUR)
- Block specific currencies
- Flag unusual currencies for review

### Human Override Triggers

Define conditions that always require human review regardless of other rules:
- New vendor (first invoice from a supplier)
- Amount above X regardless of threshold
- Specific expense categories
- Invoices without PO numbers

## Policy Evaluation Order

Rules are evaluated in this order:
1. Amount threshold check
2. Supplier verification check
3. Currency allowlist check
4. PO number check
5. Human override triggers
6. Custom rules (if configured)

The first BLOCK result stops evaluation. The first APPROVE result
(with no subsequent BLOCK) routes to the approval queue.

## Viewing Policy Decisions

Every policy evaluation is recorded in the audit trail. For each execution
you can see exactly which rules were evaluated and whether they passed or failed.
```

---

### docs/platform/audit-trail.mdx

```mdx
---
title: Audit Trail
description: Every action Clendan takes is logged to an immutable audit trail.
---

# Audit Trail

Every action taken by every worker is written to the immutable audit trail
before the response is returned. Records cannot be edited or deleted.

## What Is Logged

For every execution:

```json
{
  "trace_id": "trace-a1b2c3d4",
  "worker": "Invoice Processing Worker",
  "worker_version": "1.2",
  "timestamp": "2026-05-20T09:14:52Z",
  "actor": "system",
  "input": {
    "document": "invoice_acme_0041.pdf",
    "vendor": "Acme Supplies Ltd",
    "amount_minor": 124000,
    "currency": "GBP",
    "confidence": 0.97
  },
  "policy_evaluation": {
    "amount_threshold_check": "PASS",
    "supplier_verified_check": "PASS",
    "currency_allowlist_check": "PASS",
    "po_match_check": "PASS"
  },
  "decision": "APPROVAL_REQUIRED",
  "actions_taken": [
    "Approval request sent to sarah@company.com"
  ],
  "duration_ms": 1847,
  "model_version": "claude-sonnet-4-6"
}
```

## Accessing the Audit Trail

**Dashboard:** Go to **Dashboard → Audit Trail** to browse, filter, and export.

**API:**
```
GET /v1/audit?worker_type=invoice_processing&status=auto&from=2026-05-01&to=2026-05-31
```

## Exporting

Export your full audit trail as CSV or JSON for any date range.
Used for external audits, compliance reporting, and financial reviews.

From the dashboard: **Audit Trail → Export → Select date range → Download**

## Immutability Guarantee

Audit records are append-only. No UPDATE or DELETE operations are permitted
on audit log rows at the database level. This is enforced at both the
application layer and the database layer (row-level security policy).

If you require a signed certificate of audit trail integrity for compliance
purposes, contact support@clendan.com.
```

---

### docs/platform/webhooks.mdx

```mdx
---
title: Webhooks
description: Receive real-time notifications when Clendan events occur.
---

# Webhooks

Clendan can send HTTP POST requests to your endpoint when events occur.
Use webhooks to trigger actions in your own systems — without polling.

## Setting Up a Webhook

1. Go to **Dashboard → Developer API → Webhooks**
2. Click **Add webhook**
3. Enter your endpoint URL
4. Select the events to subscribe to
5. Copy your signing secret

## Available Events

| Event | Description |
|---|---|
| `execution.completed` | A worker completed an execution |
| `execution.auto_approved` | Worker auto-approved and executed |
| `approval.requested` | Worker requested human approval |
| `approval.completed` | A human approved or rejected |
| `integration.connected` | An integration was successfully connected |
| `integration.error` | An integration encountered an error |
| `fraud.flagged` | Fraud Detection Worker flagged a transaction |
| `worker.error` | A worker encountered an unrecoverable error |

## Webhook Payload

```json
{
  "event": "execution.completed",
  "timestamp": "2026-05-20T09:14:52Z",
  "data": {
    "execution_id": "exec-001",
    "worker": "invoice_processing",
    "decision": "auto_approved",
    "trace_id": "trace-a1b2c3d4"
  }
}
```

## Verifying Signatures

Every webhook includes a `Clendan-Signature` header. Always verify this
before processing to ensure the request came from Clendan.

<CodeGroup>
```python Python
import hmac
import hashlib

def verify_webhook(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

# In your webhook handler:
@app.post("/webhooks/clendan")
async def handle_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("Clendan-Signature")

    if not verify_webhook(payload, signature, WEBHOOK_SECRET):
        raise HTTPException(status_code=401)

    event = await request.json()
    # process event...
```

```javascript Node.js
const crypto = require('crypto');

function verifyWebhook(payload, signature, secret) {
  const expected = crypto
    .createHmac('sha256', secret)
    .update(payload)
    .digest('hex');
  return crypto.timingSafeEqual(
    Buffer.from(expected),
    Buffer.from(signature)
  );
}

app.post('/webhooks/clendan', express.raw({ type: 'application/json' }), (req, res) => {
  const signature = req.headers['clendan-signature'];
  if (!verifyWebhook(req.body, signature, process.env.WEBHOOK_SECRET)) {
    return res.status(401).send('Invalid signature');
  }
  const event = JSON.parse(req.body);
  // process event...
  res.status(200).send('OK');
});
```

```bash cURL
# Test your webhook endpoint manually:
curl -X POST https://your-endpoint.com/webhooks/clendan \
  -H "Content-Type: application/json" \
  -H "Clendan-Signature: YOUR_TEST_SIGNATURE" \
  -d '{"event": "execution.completed", "data": {}}'
```
</CodeGroup>

## Retries

If your endpoint returns a non-2xx response, Clendan retries the webhook:

| Attempt | Delay |
|---|---|
| 1st retry | 5 seconds |
| 2nd retry | 30 seconds |
| 3rd retry | 5 minutes |
| 4th retry | 30 minutes |
| 5th retry | 2 hours |

After 5 failed attempts the webhook is marked as failed and you'll be
notified by email.

## Best Practices

- Always verify the signature before processing
- Return `200 OK` immediately — process asynchronously
- Make your webhook handler idempotent — the same event may arrive more than once
- Store the `trace_id` for debugging
```

---

### docs/guides/process-first-invoice.mdx

```mdx
---
title: Process Your First Invoice
description: End-to-end guide — from PDF to bill in QuickBooks in under 60 seconds.
---

# Process Your First Invoice

This guide walks through processing a real invoice end to end using the
Invoice Processing Worker.

## Prerequisites

- Clendan account created
- QuickBooks or Xero connected (see [Connect Xero](/guides/connect-xero))
- Invoice Processing Worker deployed

## Option A — Via the Dashboard

1. Go to **Dashboard → Workers**
2. Click on the Invoice Processing Worker
3. Click **Test with document**
4. Upload your invoice PDF
5. Watch the execution log in real time

The worker will:
- Parse the invoice (under 2 seconds)
- Validate against your supplier list
- Check against your policy thresholds
- Auto-approve or route to your approval queue
- Write the bill to QuickBooks/Xero if auto-approved

## Option B — Via the API

<CodeGroup>
```python Python
import requests

# Parse the invoice
with open("invoice.pdf", "rb") as f:
    parse_response = requests.post(
        "https://api.clendan.com/v1/parse/invoice",
        headers={"Authorization": "Bearer YOUR_API_KEY"},
        files={"file": f}
    )

invoice_data = parse_response.json()["data"]

# Trigger the worker
run_response = requests.post(
    "https://api.clendan.com/v1/agents/invoice-processing/run",
    headers={
        "Authorization": "Bearer YOUR_API_KEY",
        "Idempotency-Key": f"inv-{invoice_data['invoice_number']}"
    },
    json={"invoice_data": invoice_data}
)

result = run_response.json()["data"]
print(f"Decision: {result['decision']}")
print(f"Trace ID: {run_response.json()['trace_id']}")
```

```javascript Node.js
const FormData = require('form-data');
const fs = require('fs');

// Parse the invoice
const form = new FormData();
form.append('file', fs.createReadStream('invoice.pdf'));

const parseResponse = await fetch('https://api.clendan.com/v1/parse/invoice', {
  method: 'POST',
  headers: { 'Authorization': 'Bearer YOUR_API_KEY', ...form.getHeaders() },
  body: form
});

const invoiceData = (await parseResponse.json()).data;

// Trigger the worker
const runResponse = await fetch('https://api.clendan.com/v1/agents/invoice-processing/run', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_API_KEY',
    'Content-Type': 'application/json',
    'Idempotency-Key': `inv-${invoiceData.invoice_number}`
  },
  body: JSON.stringify({ invoice_data: invoiceData })
});

const result = await runResponse.json();
console.log('Decision:', result.data.decision);
```

```bash cURL
# Step 1: Parse invoice
curl -X POST https://api.clendan.com/v1/parse/invoice \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@invoice.pdf" \
  > parsed.json

# Step 2: Run worker (pass parsed data)
curl -X POST https://api.clendan.com/v1/agents/invoice-processing/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: inv-001" \
  -d @parsed.json
```
</CodeGroup>

## What Happens Next

**If auto-approved:**
- Bill created in QuickBooks/Xero automatically
- Payment scheduled for the due date
- Audit log entry written
- You receive a summary notification (if enabled)

**If approval required:**
- Approval request appears in your queue
- You (or your finance team) receive an email notification
- Approve or reject with one click
- Worker completes the action on approval

## Viewing the Result

Go to **Dashboard → Executions** to see the full execution detail including
the reasoning trace — exactly why the worker made the decision it did.
```

---

## PART 3 — REMAINING FILES (create as stubs for now)

For each of the following files, create the file with frontmatter and a
one-line placeholder. These will be filled in as the product is built:

**API Reference stubs:**
- `docs/api-reference/receipt-ocr.mdx`
- `docs/api-reference/reconciliation.mdx`
- `docs/api-reference/contract-extraction.mdx`

**Worker stubs:**
- `docs/workers/invoice-processing.mdx`
- `docs/workers/accountant.mdx`
- `docs/workers/reconciliation.mdx`
- `docs/workers/expense-control.mdx`
- `docs/workers/collections.mdx`
- `docs/workers/fraud-detection.mdx`
- `docs/workers/treasury.mdx`
- `docs/workers/revenue-recognition.mdx`

**Integration stubs:**
- `docs/integrations/overview.mdx`
- `docs/integrations/quickbooks.mdx`
- `docs/integrations/xero.mdx`
- `docs/integrations/plaid.mdx`
- `docs/integrations/stripe.mdx`
- `docs/integrations/gocardless.mdx`
- `docs/integrations/gmail.mdx`

**Platform stubs:**
- `docs/platform/organisations.mdx`
- `docs/platform/team-roles.mdx`
- `docs/platform/api-keys.mdx`

**Guide stubs:**
- `docs/guides/connect-xero.mdx`
- `docs/guides/set-approval-thresholds.mdx`
- `docs/guides/invite-your-team.mdx`
- `docs/guides/month-end-close.mdx`

Stub format for each:
```mdx
---
title: [Page Title]
description: [One line description]
---

# [Page Title]

<Note>
This page is coming soon. Content will be added as the feature is released.
</Note>
```

---

## PART 4 — LOGO FILES

Create placeholder SVG files for the logo:

`docs/logo/dark.svg` — white text on transparent background:
```svg
<svg xmlns="http://www.w3.org/2000/svg" width="120" height="32" viewBox="0 0 120 32">
  <rect x="0" y="4" width="24" height="24" rx="2" fill="none" stroke="#00C853" stroke-width="1.5"/>
  <text x="12" y="21" text-anchor="middle" font-family="monospace" font-weight="bold" font-size="14" fill="#00C853">C</text>
  <text x="36" y="22" font-family="sans-serif" font-weight="700" font-size="14" fill="#ffffff" letter-spacing="2">CLENDAN</text>
</svg>
```

`docs/logo/light.svg` — dark text on transparent background:
```svg
<svg xmlns="http://www.w3.org/2000/svg" width="120" height="32" viewBox="0 0 120 32">
  <rect x="0" y="4" width="24" height="24" rx="2" fill="none" stroke="#00C853" stroke-width="1.5"/>
  <text x="12" y="21" text-anchor="middle" font-family="monospace" font-weight="bold" font-size="14" fill="#00C853">C</text>
  <text x="36" y="22" font-family="sans-serif" font-weight="700" font-size="14" fill="#0a0a0f" letter-spacing="2">CLENDAN</text>
</svg>
```

---

## PART 5 — PUSH AND DEPLOY

After creating all files:

```bash
git add docs/
git commit -m "Add Mintlify documentation"
git push origin main
```

Mintlify auto-deploys on every push to main.
Check deployment status at https://mintlify.com/dashboard.
Docs will be live at https://docs.clendan.com after DNS propagation.
```
