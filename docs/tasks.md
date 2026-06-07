# Clendan — Tasks

---

## Workers

### Your 5 + Orchestrator

| Worker | Status |
|---|---|
| Fraud Detection | Done ✅ |
| Collections | Done ✅ |
| Revenue Recognition | Done ✅ |
| Credit Underwriting | Done ✅ |
| Compliance | Done ✅ |
| Orchestrator (advanced) | Done ✅ — sequential chaining, parallel invocation, conflict resolution |

### Coworker — 6 workers

| Worker | Status |
|---|---|
| Invoice Processing | Done ✅ |
| AI Accountant | Done ✅ |
| Receipt Processing | Done ✅ |
| Reconciliation | To build |
| Expense Control | To build |
| Treasury | To build |

---

## Dashboard — Workers Page

| Task | Status |
|---|---|
| Remove available workers grid | Done ✅ |
| Per-worker config fields in deploy form | Done ✅ |
| Pause / Resume worker | Done ✅ |
| Delete worker with inline confirmation | Done ✅ |
| **"Run test" button per worker card** — sends a test event, shows result inline | To build |
| Worker detail page — execution history, audit log, config view | To build |

---

## Dashboard — General

| Task | Status |
|---|---|
| Auth flow (sign-up → onboarding → dashboard) | Done ✅ |
| Onboarding back button + skip | Done ✅ |
| Sign out | Done ✅ |
| Backend-unreachable warning banner | Done ✅ |
| Sidebar rename Overview → Dashboard | Done ✅ |
| **Executions page — live list of agent runs with status + confidence** | To verify |
| **Approvals page — queue of decisions awaiting human review** | To verify |
| **Audit page — immutable log of all actions** | To verify |
| **Settings page — API keys, tenant config** | To verify |

---

## Integrations

### Xero
OAuth 2.0 + webhooks. Near-identical architecture to the existing QuickBooks integration.
- OAuth connect/callback/disconnect flow
- Webhook receiver (HMAC-SHA256, same as QB)
- Sync job for invoices and bills → `invoice_received` events
- `get_invoice` / `get_bill` client functions
- Status endpoint + reconnect handling

### Stripe
Webhook-driven, no OAuth (API key only).
- Webhook receiver with Stripe signature verification (`stripe-signature` header)
- `invoice.created` / `invoice.finalized` → `invoice_received` event
- `charge.succeeded` / `payment_intent.succeeded` → `transaction_posted` event
- Stripe customer → vendor mapping

### GoCardless
UK direct debit. Recurring B2B payments.
- Webhook receiver with GoCardless signature verification
- `payments.paid_out` → `transaction_posted` event
- `invoices.paid` → `invoice_received` event
- OAuth for connecting customer's GoCardless account

### Square
POS and in-person payments.
- Webhook receiver with Square HMAC-SHA256 signature verification
- `payment.created` / `payment.updated` → `transaction_posted` event
- `invoice.payment_made` → `invoice_received` event
- OAuth for connecting merchant account

### PayPal
SMB invoicing and one-off payments.
- Webhook receiver with PayPal certificate-based signature verification
- `PAYMENT.CAPTURE.COMPLETED` → `transaction_posted` event
- `INVOICING.INVOICE.PAID` → `invoice_received` event
- OAuth for connecting PayPal business account

---

## Excel Add-in

New package: `excel-addin/` — React + Office.js.

| Task | Status |
|---|---|
| Task pane scaffold (React + Office.js) | To build |
| Auth via API keys — user pastes key once | To build |
| Select range → pick worker → see results in cells | To build |
| AI Accountant: categorise selected transactions | To build |
| Invoice Processing: process selected invoice rows | To build |
| Custom functions phase 2: `=CLENDAN.CATEGORISE(A2:E2)` | To build |
| Office Add-in manifest XML | To build |
| AppSource listing | To build |

### Charts + Dashboards
Two surfaces: task pane charts (React/Recharts) and Excel-native charts via Office.js Charts API.

**"Generate Dashboard" button** — creates a `Clendan Analysis` sheet with board-ready Excel charts.

| Worker | Chart |
|---|---|
| AI Accountant | Spending by category (bar), transactions over time (line) |
| Invoice Processing | Approved vs flagged vs blocked (stacked bar), avg processing time |
| Collections | Overdue invoices by age bucket (horizontal bar), recovery rate |
| Treasury | Cash flow forecast (line), runway remaining |
| Reconciliation | Matched vs unmatched (pie), drift over time |
| Fraud Detection | Risk score distribution (histogram), flagged transaction volume |
