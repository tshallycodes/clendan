# Clendan — Upcoming Tasks

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
