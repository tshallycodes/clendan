# Clendan — Dashboard Pages Content Specification
# Based on current nav: Overview, Approvals, Executions, Audit Trail,
# Integrations, Workers, Settings, Developer API

---

## /dashboard (Overview)

### Purpose
High-level snapshot of what Clendan is doing across all active workers.
First page a user sees after login. Must communicate system health instantly.

### Stat Cards Row (4 cards)
- **Total Executions** — cumulative count since account creation. Sub-label: "+X today"
- **Pending Approvals** — count of approvals waiting for human action. Sub-label: "X expiring soon" in warning color if any expire within 2 hours
- **Invoices Processed** — total invoices handled by Invoice Processing Worker. Sub-label: "X this month"
- **Transactions Synced** — total bank transactions ingested by Accountant Worker. Sub-label: "Last sync: X mins ago"

### Active Workers Panel
- List of all deployed + running workers
- Each row: worker name, status pulse (green = running, grey = inactive), executions today, last action timestamp, "Configure" link
- Empty state: "No active workers — deploy workers to begin" with a "Deploy your first worker" CTA button

### Execution Activity Chart
- Line chart — last 7 days
- Two lines: Auto-executed (green `#00C853`) vs Approval Required (blue `#00a8cc`)
- X axis: days of week. Y axis: execution count
- Hover tooltip showing exact counts per day
- Empty state: flat line with "No executions yet" label

### Recent Executions Table
- Columns: Time | Worker | Action | Amount | Status | →
- Status badges: Auto (green), Pending (blue), Blocked (red)
- Last 10 executions, newest first
- Each row clickable — opens execution detail in Audit Trail
- "View all executions →" link at bottom

### System Status Bar (bottom of page)
- Shows connection status of each integration: Xero ✓ / QuickBooks ✓ / Plaid ✓
- Red indicator if any integration is disconnected or erroring
- "Last health check: X seconds ago"

---

## /dashboard/approvals (Approvals)

### Purpose
Human review queue. Finance Manager comes here to approve or reject
decisions the workers flagged as requiring human sign-off.

### Queue Filters (tabs)
- All | Pending | Approved | Rejected | Expired

### Approval Card (each pending item)
- Vendor name + invoice reference
- Amount (formatted, with currency)
- Worker that submitted it (e.g. "Invoice Processing Worker")
- Time waiting — e.g. "Waiting 24 minutes"
- Expiry countdown — "Expires in 1h 42m" in warning color if under 2 hours
- Reasoning summary — one-line explanation from the worker e.g. "Amount £3,800 exceeds auto-approve threshold of £500"
- Two buttons: **Approve** (green) and **Reject** (red outlined)
- "View full trace" link — opens the reasoning trace modal

### Reasoning Trace Modal
- Full structured trace in monospace:
  - Decision requested by worker
  - Input data summary
  - Policy check results (each rule, pass/fail)
  - Confidence score
  - Worker version
  - Trace ID
- Close button

### Bulk Actions
- Checkbox per card — select multiple
- "Approve selected" and "Reject selected" bulk action buttons
- Confirmation dialog before bulk action executes

### Empty State
- "No pending approvals — workers are executing autonomously"
- Green pulse indicator

### Resolved Tab
- Table of all past approvals: who approved/rejected, timestamp, amount, outcome
- Filterable by date range
- Exportable as CSV

---

## /dashboard/executions (Executions)

### Purpose
Full log of every execution that has run — searchable, filterable, detailed.
Different from Audit Trail (which is immutable compliance log). Executions
is the operational view.

### Filters Row
- Worker type dropdown (All Workers / Invoice Processing / Accountant / etc.)
- Status filter (All / Auto / Pending / Blocked)
- Date range picker
- Search by vendor name, amount, trace ID

### Executions Table
- Columns: Timestamp | Worker | Action | Input | Amount | Outcome | Duration | →
- Outcome badges: Auto (green), Approved (green outlined), Rejected (red), Blocked (red), Pending (blue)
- Duration in ms — flag anything above 5000ms in warning color
- Pagination: 25 per page

### Execution Detail Drawer (opens on row click)
- Full execution summary:
  - Worker name + version
  - Input document reference (invoice filename, transaction ID etc.)
  - Extracted data (structured JSON view)
  - Policy check results (each rule evaluated)
  - Decision + confidence score
  - Actions taken (e.g. "Bill created in Xero — ID: BILL-4421")
  - Duration breakdown
  - Trace ID (copyable)
- If status is Pending: show Approve/Reject buttons inline

### Stats Summary Bar (above table)
- Total executions in filtered range
- Auto-executed %
- Average duration
- Blocked count

---

## /dashboard/audit-trail (Audit Trail)

### Purpose
Immutable compliance log. Every action ever taken by any worker. Cannot be
edited or deleted. This is what external auditors and regulators see.
Must feel serious and trustworthy.

### Important Note in UI
- Static banner at top: "This log is immutable. Records cannot be edited or deleted."
- Displayed in muted color, not alarming — just factual

### Filters Row
- Worker type
- Action type (invoice_created, payment_scheduled, approval_requested, etc.)
- Date range
- Status
- Search by trace ID, vendor, amount

### Audit Table
- Columns: Timestamp | Actor | Worker Version | Action | Entity | Decision | Trace ID
- Actor is either worker name or human name (for approval decisions)
- Trace ID copyable — monospace, muted color
- Row click expands full reasoning trace inline

### Expanded Reasoning Trace (inline)
```
Trace ID:       trace-a1b2c3d4
Worker:         Invoice Processing Worker v1.2
Timestamp:      2026-05-20T09:14:52Z
Actor:          system

Input:
  Document:     invoice_acme_0041.pdf
  Vendor:       Acme Supplies Ltd
  Amount:       124000 (minor units) / £1,240.00
  Currency:     GBP
  Confidence:   0.97

Policy Evaluation:
  amount_threshold_check:     PASS (£1,240 < auto limit £500? NO → approval required)
  supplier_verified_check:    PASS (Acme Supplies Ltd in approved list)
  currency_allowlist_check:   PASS (GBP allowed)
  po_match_check:             PASS (PO-2026-0089 matched)

Decision:       APPROVAL_REQUIRED
Outcome:        Approved by Sarah Chen at 2026-05-20T09:14:51Z

Actions Taken:
  1. Bill created in QuickBooks — ID: BILL-4421
  2. Payment scheduled — 2026-06-15
  3. Audit log written

Duration:       1,847ms
Model Version:  claude-sonnet-4-6
```

### Export
- Export full audit trail as CSV or JSON for a date range
- Used for external audits and compliance reporting

---

## /dashboard/integrations (Integrations)

### Purpose
Connect, manage, and monitor all external system connections.
This is where the Tool Registry is surfaced to the user.

### Connected Integrations Section
- Card per connected integration
- Each card shows:
  - Integration logo/name
  - Connection status (Connected / Error / Disconnected)
  - Last successful sync timestamp
  - Data synced (e.g. "1,240 transactions · 89 invoices")
  - "Resync now" button
  - "Disconnect" button (with confirmation dialog)
  - "View sync log" link

### Available Integrations Section
- Grid of integrations not yet connected, grouped by category:
  - **Accounting:** Xero, QuickBooks, FreshBooks, Sage
  - **Banking:** Plaid, TrueLayer, Codat
  - **Payments:** Stripe, GoCardless, Adyen
  - **ERP:** NetSuite, SAP, Microsoft Dynamics
  - **CRM:** Salesforce, HubSpot
- Each card: logo, name, description, "Connect" button
- V2/V3 integrations shown but greyed out with "Coming soon" badge

### Integration Connection Flow (on clicking Connect)
1. OAuth redirect to integration provider
2. Callback received — "Connecting..." loading state
3. Confirmation — "Connected successfully"
4. Initial sync triggered automatically — progress bar shown
5. Sync complete — "X records imported" confirmation
6. Integration card moves to Connected section

### Sync Log Modal
- Full log of sync events: timestamp, records synced, errors, duration
- Error details expandable — shows raw error mapped to structured message

---

## /dashboard/workers (Workers)

### Purpose
Deploy, configure, monitor, and manage all AI worker sub-agents.

### Deployed Workers Section
- Card per deployed worker
- Each card:
  - Worker name + version badge
  - Status: Running (green pulse) / Paused / Error
  - Autonomy level badge: Auto / Approve / Suggest
  - Executions today / this month
  - Connected tools (pill list: Xero, Plaid, etc.)
  - Last execution timestamp
  - "Configure" button → opens config drawer
  - "Pause / Resume" toggle
  - "View executions" link

### Worker Config Drawer (on Configure click)
- **Role** — read-only, set at deployment
- **Autonomy Level** — dropdown: Auto / Approve Required / Suggest Only
- **Approval Thresholds** — e.g. Auto under £X, Approve £X–£Y, Block above £Y
- **Connected Tools** — toggle which integrations this worker can access
- **Policy Rules** — add/remove rules for this worker
- **Notifications** — who gets notified on approval requests, blocks, errors
- Save button (confirms changes)

### Available Workers Section
- Grid of all workers not yet deployed — MVP/V2/V3 phases shown
- MVP workers: full "Deploy" button
- V2 workers: "Deploy" button with "Coming soon" tooltip
- V3 workers: greyed out, no button
- Each card: worker name, description, what it does, tools it needs

### Deploy Worker Flow (on Deploy click)
1. Select autonomy level
2. Set approval thresholds
3. Select connected integrations (only connected ones shown)
4. Review and confirm
5. Worker deployed — appears in Deployed Workers section

---

## /dashboard/settings (Settings)

### Purpose
Account-level configuration. Company profile, team, notifications, billing.

### Sub-sections (tabs or sub-nav)

**Company Profile**
- Company name
- Industry
- Company size
- Timezone
- Save button

**Team**
- List of team members: name, email, role, last active, Remove button
- Roles: Admin / Approver / Viewer
  - Admin: full access, can configure workers and integrations
  - Approver: can approve/reject in the approval queue only
  - Viewer: read-only access to executions and audit trail
- "Invite team member" button — email input + role selector + Send invite
- Pending invites list

**Notifications**
- Toggle: Email notification on approval request
- Toggle: Email notification on blocked execution
- Toggle: Email notification on integration error
- Toggle: Weekly execution summary email
- Notification email address (defaults to account email, can change)

**Billing**
- Current plan name + price
- Usage this month: executions used / limit, API calls used / limit
- Upgrade plan button
- Payment method (last 4 digits of card)
- Billing history table: date, amount, invoice PDF download

**Danger Zone**
- "Pause all workers" — stops all execution without deleting config
- "Delete account" — confirmation required, irreversible warning shown

---

## /dashboard/developer-api (Developer API)

### Purpose
For technical users integrating Clendan's APIs directly into their own systems.

### API Keys Section
- List of existing API keys: name, created date, last used, permissions, Revoke button
- Each key shows prefix only (e.g. `clen_live_sk_...`) — full key shown only once at creation
- "Create new API key" button:
  - Name the key
  - Set permissions: read-only / read-write / admin
  - Key shown once in a copyable field with warning "Copy this now — it will not be shown again"

### API Reference Quick Links
- Links to Mintlify docs sections:
  - Authentication
  - Invoice Parser API
  - Receipt OCR API
  - Document Reconciliation API
  - Fraud Signal API
  - Contract Extraction API
  - Webhooks

### Webhook Configuration
- List of configured webhook endpoints: URL, events subscribed, status
- "Add webhook" button:
  - Endpoint URL
  - Events to subscribe (checkboxes): execution.completed, approval.requested, integration.error, fraud.flagged
  - Signing secret shown (for verifying webhook signatures)
- Test webhook button — sends a test payload to the endpoint

### Usage Stats
- API calls this month: count + chart by day
- Breakdown by endpoint
- Error rate percentage
- Average response time

### Code Examples
- Quickstart snippet in Python and Node.js showing:
  - Authentication header
  - A simple Invoice Parser API call
  - Handling the response

---

## Global UI Rules Across All Pages

- Every page has a page title (H2, Syne bold) and a subtitle in IBM Plex Mono muted
- Loading states: skeleton loaders only — no spinners, no blank screens
- Empty states: always include a message and a CTA where relevant
- Error states: structured message, never raw API errors, always include a retry action
- All tables are sortable by column header click
- All tables have a CSV export option
- All monetary amounts display as formatted currency (£1,240.00) — stored as integer pence internally
- Trace IDs always shown in monospace, always copyable
- No page auto-refreshes — use polling with clear "Last updated X seconds ago" indicator
- Mobile: sidebar collapses to hamburger, tables become card stacks
