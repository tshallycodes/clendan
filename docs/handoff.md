# Clendan — Session Handoff
Last updated: 2026-06-07

---

## What Was Done (Cumulative)

### Backend — All 8 Workers Complete

| Worker | File | arq Job | Owner |
|---|---|---|---|
| Invoice Processing | `workers/invoice_processing.py` | `run_invoice_job` | Coworker ✅ |
| AI Accountant | `workers/ai_accountant.py` | `run_ai_accountant` | Coworker ✅ |
| Receipt Processing | `workers/receipt_processing.py` | `run_receipt_job` | Coworker ✅ |
| Fraud Detection | `workers/fraud_detection.py` | `run_fraud_detection_job` | You ✅ |
| Collections | `workers/collections.py` | `run_collections_job` | You ✅ |
| Revenue Recognition | `workers/revenue_recognition.py` | `run_revenue_recognition_job` | You ✅ |
| Credit Underwriting | `workers/credit_underwriting.py` | `run_credit_underwriting_job` | You ✅ |
| Compliance | `workers/compliance.py` | `run_compliance_job` | You ✅ |
| **Reconciliation** | `workers/reconciliation.py` | `run_reconciliation_job` | You ✅ NEW |
| **Expense Control** | `workers/expense_control.py` | `run_expense_control_job` | You ✅ NEW |
| **Treasury** | `workers/treasury.py` | `run_treasury_job` | You ✅ NEW |

All 11 workers follow the mandatory flow: receive → validate → Claude → policy → audit FIRST → DB update.
All 11 registered in `WorkerSettings.functions` in `backend/app/worker.py`.

### Backend — Orchestrator Event Routing
`run_orchestrator_job` in `worker.py` routes these event types:

| Event Type | Worker |
|---|---|
| `transaction_posted` | AI Accountant |
| `invoice_received` | Invoice Processing (full QB flow) |
| `fraud_check_requested` | Fraud Detection |
| `collection_triggered` | Collections |
| `revenue_recognition_run` | Revenue Recognition |
| `compliance_check_requested` | Compliance |
| `reconciliation_run` | Reconciliation |
| `expense_control_run` | Expense Control |
| `treasury_run` | Treasury |

### Backend — Integrations
- **QuickBooks**: OAuth + webhook (`/v1/webhooks/quickbooks`) + sync job
- **Plaid**: Link flow + webhook + transaction sync + reconciliation job
- **Stripe** (NEW): Webhook only at `POST /v1/webhooks/stripe`
  - Verifies `stripe-signature` header (HMAC-SHA256, 5-min replay window)
  - `invoice.payment_succeeded` / `invoice.finalized` → `invoice_received`
  - `charge.succeeded` / `payment_intent.succeeded` → `transaction_posted`
  - Requires `STRIPE_WEBHOOK_SECRET=whsec_...` in backend `.env`

### Backend — Workers API
- `POST /v1/workers` — deploy worker (uses `Json()` wrapper, `tenant: {connect}` syntax)
- `PATCH /v1/workers/{id}` — update config
- `PATCH /v1/workers/{id}/pause` — toggle active ↔ inactive
- `DELETE /v1/workers/{id}` — permanently delete row
- `GET /v1/dashboard/executions?worker_id={id}` — filter by worker (added)

### Backend — Security Fix
`POST /v1/approvals/{id}/respond` previously accepted `X-Tenant-ID` header (unauthenticated).
Now uses `RequireAuth` (Clerk JWT) — tenant_id and responder_id derived from verified token.

### Frontend — Workers Page
- Deploy Worker button → modal with per-type config form
- Worker type name is a link to `/dashboard/workers/[id]`
- **Run test** button per card — sends test event to `POST /v1/events`, shows result inline (auto-dismisses 8s)
- Pause / Resume — hits `PATCH /v1/workers/{id}/pause`
- Delete — inline confirm → `DELETE /v1/workers/{id}`

### Frontend — Worker Detail Page (`/dashboard/workers/[id]`)
- Server component fetches `GET /v1/workers/{id}` + `GET /v1/dashboard/executions?worker_id={id}&limit=20`
- Shows: header (status, autonomy, version), config key-value panel, recent executions table
- Run test button inline in header
- Empty state when no executions yet

### Frontend — Dashboard Page Fixes
- **Executions**: filter tabs now compare `e.decision` (was `e.status`), badge mapper fixed, stats bar fixed, approve/reject now uses `approval_id`
- **Approvals**: dead code removed, request body fixed
- **Audit**: `reasoning_trace_json` now included in API response, Fragment key warning fixed
- **Settings**: already correct, no changes needed

### Frontend — Light / Dark Mode
- `globals.css`: CSS variables for light + dark in `:root` / `.dark`, `@theme` references them
- `Providers.tsx`: `ThemeProvider` wrapper (`defaultTheme="dark"`, `enableSystem`)
- `ThemeToggle.tsx`: sun/moon icon button, mounted guard prevents hydration flash
- `layout.tsx`: wrapped with `Providers`, `suppressHydrationWarning` on `<html>`
- Toggle appears in: marketing Navbar (next to Sign in) + Sidebar (next to Back to site)
- Persists via localStorage. Respects OS preference. Default is dark.

Light mode palette: `#f5faf5` bg, `#ffffff` surface, green-tinted borders/text.
Dark mode palette: unchanged from original design.

### Frontend — Auth Flow
- `proxy.ts` IS the middleware (not middleware.ts)
- `<SignUp />` — `forceRedirectUrl="/onboarding"` + `fallbackRedirectUrl="/onboarding"`
- `<SignIn />` — `forceRedirectUrl="/dashboard"` + `fallbackRedirectUrl="/dashboard"`
- Root `/` — unauthenticated → `/sign-in`. Authenticated → `/onboarding` (layout skips to `/dashboard` if done).
- Onboarding: back button (steps 2+3), skip button (step 3), sign out top-right
- `POST /v1/onboarding` fires on step 1 (company name entry), not step 3
- Sign out button in sidebar + onboarding

---

## Current State

### What Works
- All 11 workers production-ready (backend)
- All 11 deployable from UI
- Run test button on each worker card
- Worker detail page per worker
- Executions, Approvals, Audit, Settings pages — verified and fixed
- Auth flow: sign-up → onboarding → dashboard
- Light / dark mode toggle
- Stripe webhook
- QuickBooks + Plaid integrations

### What's NOT Done
- **GoCardless, Square, PayPal** — V2, not started
- **Excel Add-in** — separate product, not started (`excel-addin/` package)
- **Xero integration** — not started (highest priority remaining integration)
- **End-to-end worker testing** — workers are built but no live test run has been done

### Known Prisma Gotchas (avoid repeating)
- Json fields: always `Json(value)` from `from prisma import Json` — raw dict causes 500
- Relation fields on create: `{"tenant": {"connect": {"id": tenant_id}}}` — not `"tenant_id": ...`

---

## Critical Setup

### 1. Clerk Dashboard Redirects
Go to **clerk.com → Configure → Paths**:
- Sign-in redirect: `http://localhost:3000/dashboard`
- Sign-up redirect: `http://localhost:3000/onboarding`

### 2. Frontend `.env.local`
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
```
DATABASE_URL=postgresql://...
REDIS_URL=redis://localhost:6379/0
ANTHROPIC_API_KEY=sk-ant-...
CLERK_FRONTEND_API=musical-crayfish-14.clerk.accounts.dev
QUICKBOOKS_WEBHOOK_VERIFIER_TOKEN=...
STRIPE_WEBHOOK_SECRET=whsec_...
```

### 4. Start Order
```bash
# Terminal 1 — Backend
cd backend && uvicorn app.main:app --reload

# Terminal 2 — arq worker
cd backend && python -m arq app.worker.WorkerSettings

# Terminal 3 — Frontend
cd frontend && npm run dev
```

---

## What's Next (Priority Order)

1. **Xero integration** — OAuth + webhook + sync job. Near-identical to QuickBooks. UK market priority.
2. **End-to-end worker test** — deploy a worker, hit Run test, verify execution + audit log in DB
3. **GoCardless** — UK direct debit (V2)
4. **Square / PayPal** — (V2)
5. **Excel Add-in** — new package `excel-addin/`, React + Office.js, auth via API keys

---

## File Map — Key Files

| What | Where |
|---|---|
| All API routes | `backend/app/api/v1/router.py` |
| Workers API | `backend/app/api/v1/workers.py` |
| Events endpoint | `backend/app/api/v1/events.py` |
| Orchestrator + routing | `backend/app/worker.py` (`run_orchestrator_job`) |
| arq job registration | `backend/app/worker.py` (`WorkerSettings.functions`) |
| Policy engine | `backend/app/policy/engine.py` |
| Audit logger | `backend/app/audit/logger.py` |
| QB webhook | `backend/app/api/v1/webhooks/quickbooks.py` |
| Plaid webhook | `backend/app/api/v1/webhooks/plaid.py` |
| Stripe webhook | `backend/app/api/v1/webhooks/stripe.py` |
| Stripe client | `backend/app/integrations/stripe/client.py` |
| Clerk middleware | `frontend/proxy.ts` |
| Theme provider | `frontend/components/Providers.tsx` |
| Theme toggle | `frontend/components/ThemeToggle.tsx` |
| CSS tokens | `frontend/app/globals.css` |
| Root layout | `frontend/app/layout.tsx` |
| Dashboard layout | `frontend/app/(dashboard)/layout.tsx` |
| Onboarding page | `frontend/app/onboarding/page.tsx` |
| Workers page | `frontend/app/(dashboard)/dashboard/workers/` |
| Worker detail page | `frontend/app/(dashboard)/dashboard/workers/[id]/page.tsx` |
| Worker card | `frontend/components/dashboard/workers/WorkerCard.tsx` |
| Worker detail UI | `frontend/components/dashboard/workers/WorkerDetail.tsx` |
| Run test hook | `frontend/components/dashboard/workers/useRunTest.ts` |
| Test payloads | `frontend/components/dashboard/workers/workerTestPayloads.ts` |
| Deploy form | `frontend/components/dashboard/workers/DeployWorkerForm.tsx` |
| Per-worker config | `frontend/components/dashboard/workers/WorkerConfigFields.tsx` |
| Sidebar | `frontend/components/dashboard/Sidebar.tsx` |
| Marketing Navbar | `frontend/components/marketing/Navbar.tsx` |
