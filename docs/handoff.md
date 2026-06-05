# Clendan — Session Handoff
Last updated: 2026-06-05

---

## What Was Done This Session

### Backend — Workers
All 5 of the user's workers were built and are production-ready (replacing stubs):

| Worker | File | arq Job |
|---|---|---|
| Fraud Detection | `backend/app/workers/fraud_detection.py` | `run_fraud_detection_job` |
| Collections | `backend/app/workers/collections.py` | `run_collections_job` |
| Revenue Recognition | `backend/app/workers/revenue_recognition.py` | `run_revenue_recognition_job` |
| Credit Underwriting | `backend/app/workers/credit_underwriting.py` | `run_credit_underwriting_job` |
| Compliance | `backend/app/workers/compliance.py` | `run_compliance_job` |

All 5 follow the mandatory flow: receive → validate → Claude call → policy → audit FIRST → execution update.
All 5 are registered in `WorkerSettings.functions` in `backend/app/worker.py`.

Coworker's workers (Reconciliation, Expense Control, Treasury) are still stubs.

### Backend — Orchestrator
`backend/app/orchestrator/orchestrator.py` upgraded with:
- `invoke_workers_sequential` — chain workers, stop on blocked
- `invoke_workers_parallel` — asyncio.gather fan-out
- `resolve_conflict` — blocked > approval_required > highest confidence
- `handle_invoice_with_fraud_check` — Invoice Processing → Fraud Detection chain

### Backend — Events + Webhooks
- `POST /v1/events` — single orchestrator entry point, all event types routable
- `backend/app/api/v1/webhooks/quickbooks.py` — QB webhook, HMAC-SHA256 verified
- QB webhook routes Invoice/Bill creates → `invoice_received` events
- Plaid sync emits `transaction_posted` events after new transactions land
- `backend/app/orchestrator/events.py` — shared `enqueue_orchestrator_event` helper
- `backend/app/integrations/quickbooks/client.py` — added `get_invoice` and `get_bill`

### Frontend — Auth Flow
This was the biggest source of bugs this session. Fixed:
- `frontend/proxy.ts` — extended public routes list, IS the middleware (not middleware.ts)
- Deleted conflicting `middleware.ts` that was created by mistake
- `<SignUp />` — `forceRedirectUrl="/onboarding"` + `fallbackRedirectUrl="/onboarding"`
- `<SignIn />` — `forceRedirectUrl="/dashboard"` + `fallbackRedirectUrl="/dashboard"`
- Onboarding layout — checks if already onboarded and redirects to `/dashboard`
- Landing page — authenticated users → `/onboarding` (which self-redirects to `/dashboard` if already done)
- `POST /v1/onboarding` now fires on step 1 (company name) not step 3 (deploy worker)
- Sign out button added to sidebar

### Frontend — Workers Page
- Removed the available workers grid (redundant with the form dropdown)
- Single Deploy Worker button → modal with form
- Per-worker config fields in deploy form (`WorkerConfigFields.tsx`)
- All 11 worker types are deployable (backend VALID_TYPES expanded)

### Frontend — Dashboard Layout
- Shows amber warning banner when backend is unreachable
- Redirects to `/onboarding` when backend returns 404 on `/v1/tenants/me`

---

## Current State

### What Works
- All API routes registered and serving
- Auth flow: sign-up → onboarding → dashboard
- 8 workers production-ready (Invoice, AI Accountant, Receipt, Fraud, Collections, Rev Rec, Credit Underwriting, Compliance)
- Orchestrator event routing for all event types
- QB + Plaid webhooks wired into orchestrator
- Worker deploy form with per-type config
- Sign in / sign out

### What's Broken / Not Verified
- **Onboarding redirect via SSO (Google/GitHub)** — Clerk Dashboard redirect URLs must be manually set (see below). Component props alone don't control SSO redirects.
- **Dashboard shows no data** — user hasn't completed onboarding end-to-end yet; DB is empty (0 tenants, 0 users). Backend must be running when onboarding step 1 is submitted.
- **Coworker's workers** — Reconciliation, Expense Control, Treasury are still stubs in `backend/app/workers/`

---

## Critical Setup Required (Do This First)

### 1. Clerk Dashboard Redirects
Go to **clerk.com → your app → Configure → Paths** and set:
- Sign-in redirect: `http://localhost:3000/dashboard`
- Sign-up redirect: `http://localhost:3000/onboarding`

Without this, Google/GitHub SSO redirects to `/` instead of `/onboarding`.

### 2. Frontend `.env.local`
Make sure these are set:
```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/dashboard
NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/onboarding
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3. Backend `.env`
Required fields (check `backend/app/core/config.py` for full list):
```
DATABASE_URL=postgresql://...
REDIS_URL=redis://localhost:6379/0
ANTHROPIC_API_KEY=sk-ant-...
CLERK_FRONTEND_API=musical-crayfish-14.clerk.accounts.dev   # from your Clerk dashboard
QUICKBOOKS_WEBHOOK_VERIFIER_TOKEN=...   # from Intuit developer console
```

### 4. Start Order
```bash
# Terminal 1 — Backend
cd backend && uvicorn app.main:app --reload

# Terminal 2 — arq worker (for background jobs)
cd backend && python -m arq app.worker.WorkerSettings

# Terminal 3 — Frontend
cd frontend && npm run dev
```

### 5. First Run
1. Go to `http://localhost:3000` → click Get started
2. Sign up → lands on `/onboarding`
3. Enter company name → click Next (this calls `POST /v1/onboarding` and creates tenant + user in DB)
4. Skip integrations for now
5. Deploy a worker on step 3
6. Go to Dashboard — data should now load

---

## Architecture Reminder

```
External trigger (QB webhook, Plaid, Stripe, manual)
  → POST /v1/events
  → enqueue_orchestrator_event() creates Execution record
  → run_orchestrator_job (arq)
    → routes by event_type to appropriate worker job
    → worker: Claude call → policy → audit → execution update
```

Event type → worker mapping in `backend/app/orchestrator/orchestrator.py` → `EVENT_TO_WORKER`.

Workers NEVER call each other directly. All coordination through orchestrator.

---

## What's Next (Priority Order)

### Immediate
1. **Verify end-to-end onboarding** — sign up → onboarding step 1 → check DB has tenant + user
2. **Test a worker** — deploy Fraud Detection worker, trigger `fraud_check_requested` event via curl, check execution record and audit log

### Coworker's Workers (still stubs)
- `backend/app/workers/reconciliation.py`
- `backend/app/workers/expense_control.py`
- `backend/app/workers/treasury.py`

### Integrations (see tasks.md for full spec)
- **Xero** — near-identical to QuickBooks, highest priority (UK market)
- **Stripe** — webhook only, no OAuth, maps to existing events
- **GoCardless** — UK direct debit
- **Square / PayPal** — V2

### Excel Add-in
- New package `excel-addin/` — React + Office.js
- Task pane + Deploy Worker button from within Excel
- Auth via API keys (already built at `POST /v1/api-keys`)
- Charts: both in-pane (Recharts) and native Excel charts via Office.js Charts API

---

## File Map — Key Files

| What | Where |
|---|---|
| All API routes | `backend/app/api/v1/router.py` |
| Events endpoint | `backend/app/api/v1/events.py` |
| Orchestrator | `backend/app/orchestrator/orchestrator.py` |
| Event enqueueing helper | `backend/app/orchestrator/events.py` |
| arq job registration | `backend/app/worker.py` |
| Policy engine | `backend/app/policy/engine.py` |
| Audit logger | `backend/app/audit/logger.py` |
| QB webhook | `backend/app/api/v1/webhooks/quickbooks.py` |
| Plaid webhook | `backend/app/api/v1/webhooks/plaid.py` |
| Clerk middleware | `frontend/proxy.ts` |
| Dashboard layout | `frontend/app/(dashboard)/layout.tsx` |
| Onboarding page | `frontend/app/onboarding/page.tsx` |
| Workers page | `frontend/app/(dashboard)/dashboard/workers/` |
| Worker deploy form | `frontend/components/dashboard/workers/DeployWorkerForm.tsx` |
| Per-worker config | `frontend/components/dashboard/workers/WorkerConfigFields.tsx` |
| Sidebar | `frontend/components/dashboard/Sidebar.tsx` |
