# Roadmap and Future Expansion

Clendan is deliberately scoped to **one flow: AI-powered invoice processing feeding
automated month-end close, integrated deeply with your ERP.** AP is the wedge; close is the
lock-in. Everything below is tracked here **in docs only** — it is not kept as vestigial code.
When we expand, we do it intentionally, not by accruing scope creep.

Anything not listed as "In scope today" has been **removed from the codebase**. If you are
looking for a tool or connector that used to exist and no longer does, it is here.

---

## In scope today (do not add to this file)

**AP pipeline** — invoice processing, spend control, payment runs.
**Close pipeline** — reconciliation (bank / invoice / VAT / payroll), month-end close,
payroll reconciliation, journal entries.
**Supporting** — document intelligence, financial reporting, tax compliance.
**Ingestion** — email/drive integrations (Gmail, Google Drive, Outlook, OneDrive, Dropbox).
**Connectors** — banking (Plaid, TrueLayer, Mono, GoCardless), accounting/ERP (Xero,
QuickBooks, FreshBooks, Codat, Sage, NetSuite, SAP, Dynamics), PSPs feeding reconciliation
(Stripe, PayPal, Square, Adyen, Wise), and QuickBooks bill write-back.

---

## Committed next sprint — AP/close improvements

These three close the loop on AP and make month-end close more automatic. They are the next
sprint's headline work. They are **not** implemented yet — the honest state is that the
vestigial/placeholder versions have been removed rather than left pretending to work.

1. **Real 3-way matching of invoices to purchase orders.**
   Add a `PurchaseOrder` model, sync POs from the ERP (NetSuite already exposes
   `get_purchase_orders`; others to follow), and match bill → PO → receipt in `spend_control`.
   The previous `purchase_order_ref` / `missing_po` fields were never populated by any sync,
   so they were removed; this rebuilds the feature on real PO data.

2. **Automated payout execution in Payment Runs.**
   Today `payment_run` classifies bills, creates an immutable `PaymentRun` record, and routes
   approvals — but it **schedules only; no money moves**. Real execution means wiring a payout
   rail (e.g. Wise / bank transfer) with idempotency keys, retries with backoff, a
   reconciliation job, and explicit rollback handling. Because this moves real money, it must
   land behind its own design review and staged rollout — never shipped speculatively.

3. **ERP bill write-back beyond QuickBooks.**
   QuickBooks bill write-back is live (`integrations/quickbooks/write.py`). Extend the same
   pattern to **Xero, Sage, and NetSuite** so approved invoices sync to whichever books the
   tenant runs on, not just QuickBooks. Each requires the provider's write OAuth scopes and
   live-sandbox testing before enablement.

---

## Future expansion — out of scope features (removed from code)

Tracked for when the core AP + close product is world-class. Each was deleted from the
codebase (tools, routes, config, tests, UI) as part of the AP-first restructure.

### Financial tools
- **AR & Collections** — outstanding-invoice monitoring, tiered debtor follow-ups, escalation,
  late fees, write-off controls. (was `accounts_receivable`, `collections`)
- **Treasury & Cash** — multi-bank cash position, runway/liquidity forecasting, FX exposure,
  counterparty limits, cash sweep. (was `treasury`, `cash_flow_forecast`)
- **Budgeting** — department budget vs actuals, variance analysis, overspend routing.
  (was `budgeting`; the `Budget` / `BudgetLine` DB models are retained as infrastructure)
- **Revenue Recognition** — ASC 606 / IFRS 15 recognition schedules and period lock.
  (was `revenue_recognition`)
- **Credit Underwriting** — automated credit/DTI/LTV decisioning and adverse-action notices.
  (was `credit_underwriting`)
- **Risk & Compliance / Fraud Detection** — transaction risk scoring, velocity/structuring
  detection, KYC/AML/CTR monitoring, SAR handling. (was `fraud_detection`, `compliance`)

### Standalone API tools
- **Fraud Signal API** (`POST /fraud/score`) and **Contract Extraction** (`POST /parse/contract`).

### Connectors
- **CRM** — Salesforce and HubSpot (customer, deal, and pipeline data).

### Surfaces
- **Excel add-in** — Office.js task-pane add-in.
- **MCP server** (`backend/mcp/`) — Model Context Protocol server exposing Clendan to MCP
  clients. Left in the repo but out of scope for active development.

---

*When picking up any item here: design first, review, then build — and update this file so it
always reflects what is genuinely in the product versus on the roadmap.*
