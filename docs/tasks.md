# Clendan — Upcoming Tasks

## Worker Build Plan

11 workers total. 3 already production-ready.

### You — 5 workers + Orchestrator

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

## Integrations

### Xero
OAuth 2.0 + webhooks. Near-identical architecture to the existing QuickBooks integration.
- OAuth connect/callback/disconnect flow
- Webhook receiver (Xero uses HMAC-SHA256, same as QB)
- Sync job for invoices and bills → `invoice_received` events
- `get_invoice` / `get_bill` QB-style client functions
- Status endpoint + reconnect handling

### Stripe
Payments-in integration. Webhook-driven, no OAuth needed (API key).
- Webhook receiver with Stripe signature verification (`stripe-signature` header)
- `invoice.created` / `invoice.finalized` → `invoice_received` event
- `charge.succeeded` / `payment_intent.succeeded` → `transaction_posted` event
- Stripe customer → vendor mapping

### GoCardless
UK direct debit. Recurring B2B payments and subscriptions. Strong UK market relevance.
- Webhook receiver with GoCardless signature verification (`Webhook-Signature` header)
- `payments.paid_out` → `transaction_posted` event
- `invoices.paid` → `invoice_received` event
- OAuth for connecting customer's GoCardless account

### Square
POS and in-person payments. Retail, restaurants, service businesses.
- Webhook receiver with Square HMAC-SHA256 signature verification
- `payment.created` / `payment.updated` → `transaction_posted` event
- `invoice.payment_made` → `invoice_received` event
- OAuth for connecting merchant account

### PayPal
SMB invoicing and one-off payments. Long tail of small business usage.
- Webhook receiver with PayPal certificate-based signature verification
- `PAYMENT.CAPTURE.COMPLETED` → `transaction_posted` event
- `INVOICING.INVOICE.PAID` → `invoice_received` event
- OAuth for connecting PayPal business account

### Excel Add-in (Microsoft Office Add-in)
Clendan as a task pane inside Excel. Finance teams run workers directly from their spreadsheet.
- New package: `excel-addin/` — React + Office.js
- Task pane UI: select a range → pick a worker → see results written back to cells
- Auth via existing API keys (`POST /v1/api-keys`) — user pastes key once
- Workers to expose: AI Accountant (categorise selected transactions), Invoice Processing (process selected invoice rows)
- Custom functions phase 2: `=CLENDAN.CATEGORISE(A2:E2)`
- Office Add-in manifest XML + AppSource listing

#### Charts + Dashboards
Two surfaces: charts rendered inside the task pane (React/Recharts), and Excel-native charts inserted into sheets via the Office.js Charts API.

**"Generate Dashboard" button** — creates a `Clendan Analysis` sheet with board-ready Excel charts built from processed data.

| Worker | Chart |
|---|---|
| AI Accountant | Spending by category (bar), transactions over time (line) |
| Invoice Processing | Approved vs flagged vs blocked (stacked bar), avg processing time |
| Collections | Overdue invoices by age bucket (horizontal bar), recovery rate |
| Treasury | Cash flow forecast (line), runway remaining |
| Reconciliation | Matched vs unmatched (pie), drift over time |
| Fraud Detection | Risk score distribution (histogram), flagged transaction volume |
