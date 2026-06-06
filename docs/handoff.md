# Clendan — Session Handoff
Last updated: 2026-06-06

---

## What Was Done (Cumulative)

### Backend — Workers
All 5 of the user's workers are production-ready:

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

### Backend — Workers API (latest fixes)
- `POST /v1/workers` — fixed: now uses `Json(config)` wrapper and `tenant: {connect: {id}}` relation syntax (raw dict + tenant_id scalar both caused Prisma 500)
- `PATCH /v1/workers/{id}` — config update (uses `Json()` wrapper)
- `PATCH /v1/workers/{id}/pause` — new endpoint, toggles active ↔ inactive
- `DELETE /v1/workers/{id}` — new endpoint, permanently deletes the row (previously only deactivated)

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
- `frontend/proxy.ts` — IS the middleware (not middleware.ts). Public routes list extended.
- `<SignUp />` — `forceRedirectUrl="/onboarding"` + `fallbackRedirectUrl="/onboarding"`
- `<SignIn />` — `forceRedirectUrl="/dashboard"` + `fallbackRedirectUrl="/dashboard"`
- Onboarding layout — checks if already onboarded, redirects to `/dashboard` if so
- Root `/` — unauthenticated → `/sign-in`. Authenticated → `/onboarding` (layout skips to `/dashboard` if done).
- `POST /v1/onboarding` fires on step 1 (company name), not step 3
- Sign out button in sidebar

### Frontend — Onboarding
- **← Back** button — appears on steps 2 and 3, returns to previous step
- **Sign out** button — top-right on all steps except success screen
- **Skip for now** — on step 3 (worker deploy), goes straight to `/dashboard`. Tenant already created on step 1 so this is safe.
- Error on step 3 now shows `cd backend && uvicorn app.main:app --reload` hint

### Frontend — Workers Page
- Removed the available workers grid
- Single Deploy Worker button → modal with `DeployWorkerForm`
- Per-worker config fields (`WorkerConfigFields.tsx`) — each worker type has distinct settings
- All 11 worker types deployable
- Fixed: workers list `.map is not a function` — backend returns `{data: {workers: [...]}}`, page now unwraps `.workers`
- **Delete worker** — inline confirm/cancel button on each WorkerCard
- Fixed: WorkerCard had wrong API port 8001 → corrected to 8000
- Pause/Resume now hits `PATCH /v1/workers/{id}/pause` (dedicated endpoint)

### Frontend — Dashboard Layout
- Shows amber warning banner when backend is unreachable
- Redirects to `/onboarding` when backend returns 404 on `/v1/tenants/me`

---

## Current State

### What Works
- All API routes registered and serving
- Auth flow: sign-up → onboarding → dashboard (root redirects to sign-in)
- 8 workers production-ready (Invoice, AI Accountant, Receipt, Fraud, Collections, Rev Rec, Credit Underwriting, Compliance)
- Orchestrator event routing for all event types
- QB + Plaid webhooks wired into orchestrator
- Worker deploy / pause / delete from UI
- Sign in / sign out

### What's Broken / Not Verified
- **Onboarding redirect via SSO (Google/GitHub)** — Clerk Dashboard redirect URLs must be manually set. Component props alone don't control SSO redirects.
- **Workers not yet end-to-end tested** — workers are built but no test run has been done to verify execution records + audit logs are written correctly. Next step is testing each worker in order, starting with Fraud Detection.
- **Coworker's workers** — Reconciliation, Expense Control, Treasury are still stubs in `backend/app/workers/`

---

## Critical Setup Required (Do This First)

### 1. Clerk Dashboard Redirects
Go to **clerk.com → your app → Configure → Paths** and set:
- Sign-in redirect: `http://localhost:3000/dashboard`
- Sign-up redirect: `http://localhost:3000/onboarding`

Without this, Google/GitHub SSO redirects to `/sign-in` instead of `/onboarding`.

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
1. Go to `http://localhost:3000` → redirects to `/sign-in`
2. Sign up → lands on `/onboarding`
3. Enter company name → click Next (creates tenant + user in DB via `POST /v1/onboarding`)
4. Step 2: integrations (skip for now)
5. Step 3: deploy a worker OR click "Skip for now"
6. Dashboard loads

---

## Testing Workers (Next Priority)

Test each worker in this order. For each: deploy via UI → trigger via curl → verify execution + audit log in DB.

### Fraud Detection
```bash
# Trigger a fraud check event
curl -X POST http://localhost:8000/v1/events \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "fraud_check_requested",
    "payload": {"transaction_ids": ["<txn_id>"]},
    "idempotency_key": "test-fraud-001"
  }'
```
Verify: `SELECT * FROM executions ORDER BY created_at DESC LIMIT 1;`
Verify: `SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 1;`

### Collections
Event type: `collection_triggered`
Payload: `{"invoice_ids": ["<invoice_id>"]}`

### Revenue Recognition
Event type: `revenue_recognition_run`
Payload: `{"invoice_ids": ["<invoice_id>"]}`

### Credit Underwriting
Event type: (check `orchestrator.py` EVENT_TO_WORKER map)

### Compliance
Event type: `compliance_check_requested`
Payload: `{"transaction_ids": ["<txn_id>"]}`

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

**Prisma Python notes (avoid repeating these bugs):**
- Json fields: always wrap with `Json(value)` from `from prisma import Json`
- Relation fields on create: use `{"tenant": {"connect": {"id": tenant_id}}}`, not `"tenant_id": tenant_id`

---

## What's Next (Priority Order)

1. **Test all 5 workers end-to-end** — in order: Fraud Detection → Collections → Revenue Recognition → Credit Underwriting → Compliance
2. **Coworker's workers** — Reconciliation, Expense Control, Treasury (still stubs)
3. **Integrations** — Xero (highest priority, UK market), Stripe, GoCardless, Square/PayPal
4. **Excel Add-in** — `excel-addin/` package, React + Office.js, auth via API keys

---

## File Map — Key Files

| What | Where |
|---|---|
| All API routes | `backend/app/api/v1/router.py` |
| Workers API | `backend/app/api/v1/workers.py` |
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
| Worker card (pause/delete) | `frontend/components/dashboard/workers/WorkerCard.tsx` |
| Worker deploy form | `frontend/components/dashboard/workers/DeployWorkerForm.tsx` |
| Per-worker config | `frontend/components/dashboard/workers/WorkerConfigFields.tsx` |
| Sidebar | `frontend/components/dashboard/Sidebar.tsx` |
