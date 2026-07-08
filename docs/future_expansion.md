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

## Expansion roadmap — prioritised (removed from code)

Each item below was deleted from the codebase (tools, routes, config, tests, UI) in the
AP-first restructure. They come back **intentionally and in priority order**, not by scope
creep. The litmus test for staying on the roadmap: **same buyer + same data spine** — the
buyer is the controller / finance-ops lead who owns the books, and the spine is ERP + bank +
document ingestion. A module that needs a *different* buyer or a *different* regulatory/data
world is a different product and is dropped below.

### Tier 1 — Core expansion (completes the product's shape)

The full thesis is *"we run your payables, receivables, and close."* This is the one new
workflow that gets us there.

- **AR & Collections** — outstanding-invoice monitoring, tiered debtor follow-ups, escalation,
  late fees, write-off controls. The mirror of AP (money in vs money out), same buyer, same
  data spine (customer invoices are already synced read-only). Highest-impact next workflow —
  build it once the AP loop is fully closed (real payouts + PO matching + ERP write-back).
  (was `accounts_receivable`, `collections`)

### Tier 2 — Close-pipeline tools (extend Close, not new workflows)

These are **not** separate pipelines — they are additional tools *inside* the Close
workflow, run at month-end on the period's locked actuals and feeding Financial Reporting.
There are really only three workflows (AP, Close, AR & Collections); Close is the pipeline
that accretes close-time tools over time. Build these once the core trio is excellent.

- **Revenue Recognition** — ASC 606 / IFRS 15 recognition schedules and period lock. A close
  step: post deferred → recognised revenue journal entries during month-end, then lock.
  Narrow (mostly SaaS/subscription) and edge-case heavy — build **only if** we target SaaS.
  (was `revenue_recognition`)
- **Budget vs actuals (variance)** — overlay the budget on the period's actuals, flag
  variances, route overspend. A close-time reporting overlay; cheap because actuals are
  already synced. (the reporting half of the old `budgeting`; `Budget` / `BudgetLine` models
  retained as infrastructure)

Budget *planning/creation* (setting next period's numbers) is a separate upfront FP&A
activity on a different cadence — **not** part of close. Deferred, low priority.

### Tier 3 — Deferred (different buyer)

- **Treasury & Cash** — multi-bank cash position, runway/liquidity forecasting, FX exposure,
  counterparty limits, cash sweep. Useful, but this is a CFO/treasury-desk tool with its own
  data model — a step away from the controller buyer. Revisit only when moving upmarket to
  CFOs. (was `treasury`, `cash_flow_forecast`)

### Not planned — off-thesis (different product)

Fails the litmus test: different buyer, different regulatory regime, different data. Not
"automate your accounting." Kept here only so the decision is recorded.

- **Credit Underwriting** — automated credit/DTI/LTV decisioning and adverse-action notices.
  This is a *lending* product (lender buyer, consumer-credit regulation). **Dropped.**
  (was `credit_underwriting`)
- **Risk & Compliance / Fraud Detection** — transaction risk scoring, velocity/structuring
  detection, KYC/AML/CTR monitoring, SAR handling. This is *bank/fintech-grade compliance*
  (regulated-institution buyer, heavy liability). **Dropped** — the only fraud surface we keep
  is the lightweight suspicious-payable flagging that already lives inside `spend_control`.
  (was `fraud_detection`, `compliance`)

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
