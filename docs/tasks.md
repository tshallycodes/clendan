# Clendan — Build Task Tracker

All phases from master-build-prompt.md. Each session builds ONE phase, confirms green, then stops.

---

## FOUNDATION ✅ COMPLETE (2026-06-02)

- [x] Scaffold repo structure (frontend/, backend/, prisma/, tests/)
- [x] `frontend/` — Next.js 16 (App Router, TypeScript, Tailwind, shadcn/ui deps, Vitest)
- [x] `backend/app/core/config.py` — Pydantic Settings v2, all config from env vars
- [x] `backend/app/core/db.py` — Prisma client singleton
- [x] `backend/app/core/security.py` — Clerk JWT verification via JWKS
- [x] `backend/app/core/logging.py` — Structured JSON logging with ContextVar trace IDs
- [x] `backend/app/main.py` — FastAPI app factory, CORS, trace middleware, `/health`, `/ready`
- [x] `backend/prisma/schema.prisma` — 8 models: Tenant, User, Integration, Worker, Execution, Approval, AuditLog, Invoice
- [x] `docker-compose.yml` — Postgres 16 + Redis 7 + backend
- [x] `.env.example` — all required variables listed
- [x] `.gitignore`, `README.md`
- [x] Backend smoke tests: 2/2 passing (`/health`, `/ready`)
- [x] Frontend smoke test: 1/1 passing
- [x] Frontend build: compiled successfully

---

## PHASE 1 — Invoice Parser + Policy + Audit + Worker

> Start only after foundation confirmed green. ✅ Ready.

### 1.1 Invoice Parser API — `POST /v1/parse/invoice`
- [ ] Accept PDF/PNG/JPG upload
- [ ] Call Claude (Anthropic SDK) to extract: vendor, invoice_number, line_items, amount_minor (integer), currency, due_date, vat, po_number, confidence
- [ ] Pydantic output model — validate before returning; empty/low-confidence is not success
- [ ] Idempotency-Key header support
- [ ] Standard response shape: `{ data, error, trace_id, timestamp }`

### 1.2 Policy Engine — `app/policy/`
- [ ] Deterministic rule evaluation on every worker output
- [ ] Rule: amount threshold — auto under X, approve X–Y, block above Y
- [ ] Rule: verified-supplier check
- [ ] Rule: currency allow-list
- [ ] Pure functions, no side effects
- [ ] Full unit test coverage of all branches

### 1.3 Audit Logger — `app/audit/`
- [ ] Append-only writes to AuditLog table
- [ ] Full reasoning trace stored, never truncated
- [ ] If audit write fails → operation fails (no silent success)
- [ ] Unit tests: confirm append-only behaviour

### 1.4 Invoice Processing Worker — `app/workers/invoice_processing.py`
- [ ] Clear interface callable by Orchestrator as a tool
- [ ] Flow: parse → validate supplier → policy check → decision → mock accounting write → audit → return
- [ ] Currency as integer minor units throughout; format only at display edge
- [ ] Three outcomes: auto-approved, approval-required, blocked

### 1.5 Execution API — `POST /v1/agents/{worker_id}/run`
- [ ] Idempotent — same idempotency key returns same result
- [ ] Runs worker through BullMQ queue (not in request thread)
- [ ] Scoped to tenant; RLS enforced at DB AND app layer
- [ ] Standard response shape

### 1.6 Approval API — `POST /v1/approvals/{id}/respond`
- [ ] Approve / reject actions
- [ ] Enforces approval expiry TTL — stale approvals rejected
- [ ] Scoped to tenant

### 1.7 Queue Wiring
- [ ] BullMQ + Redis integration
- [ ] Worker execution runs via queue, not in request thread
- [ ] Dead-letter queue for failed jobs

### 1.8 Tests
- [ ] Unit: policy engine — all branches (auto / approve / block)
- [ ] Unit: currency rounding
- [ ] Unit: audit append behaviour
- [ ] Integration: auto-approved execution end-to-end
- [ ] Integration: approval-required execution end-to-end
- [ ] Integration: blocked execution end-to-end
- [ ] Proof: blocked case → no accounting write occurred

---

## PHASE 2 — Auth + Tenant Onboarding + RLS Verification ✅ COMPLETE (2026-06-03)

### Backend
- [x] `require_auth` Clerk JWT verification via JWKS (`app/core/security.py`)
- [x] `RequireAuth` annotated dependency type for all route files
- [x] `POST /v1/onboarding` — idempotent tenant + user creation on first sign-in
- [x] `GET /v1/tenants/me` — returns authenticated user's tenant (scoped by clerk_user_id)
- [x] `app/api/v1/router.py` + `app/core/responses.py` + `app/models/schemas.py`

### Frontend (Next.js 16)
- [x] `@clerk/nextjs@7.4.3` installed, `ClerkProvider` in `layout.tsx`
- [x] `proxy.ts` — Next.js 16 file convention (replaces deprecated `middleware.ts`); conditional Clerk loading; dev fallback redirects `/dashboard` → `/sign-in`
- [x] Sign-in + sign-up pages (`app/(auth)/`)
- [x] `app/(dashboard)/layout.tsx` — server-side auth check
- [x] `lib/auth.ts` — `getAuthHeaders()` / `getBackendToken()`

### Database RLS
- [x] `backend/migrations/001_enable_rls.sql` — RLS + `FORCE ROW LEVEL SECURITY` on all 8 tables
- [x] `tenant_context()` async context manager sets `app.current_tenant_id` per transaction

### Tests
- [x] `test_auth.py` — 7 tests: protected routes return 401/403, public routes return 200
- [x] `test_tenant_isolation.py` — missing user returns 404 not another tenant's data; integration test skipped (requires live DB + RLS applied)
- [x] Backend: **12 passed, 1 skipped** · Frontend: **1/1 Vitest** · TypeScript: clean
- [x] Playwright verified: home ✅ · /dashboard→/sign-in redirect ✅ · sign-in UI ✅ · sign-up UI ✅

### Still required before Phase 2 is production-ready
- [ ] Add real Clerk keys to `.env.local` (`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` + `CLERK_SECRET_KEY`)
- [ ] Apply RLS to live DB: `psql $DATABASE_URL -f backend/migrations/001_enable_rls.sql`
- [ ] Run full integration test: `pytest -m integration` against live DB

---

## PHASE 3 — QuickBooks Integration (real, behind mocked interface)

- [ ] OAuth flow: auth → callback → encrypted token store
- [ ] Initial sync after connect
- [ ] Polling until data confirmed present
- [ ] Mark integration as connected
- [ ] Swap mock accounting write (Phase 1) for real QuickBooks client
- [ ] Circuit breaker + retry with backoff on all QuickBooks calls
- [ ] Encrypted credential storage (tenant-specific keys)
- [ ] Error mapping — never expose raw QuickBooks errors to frontend

---

## PHASE 4 — Plaid Integration + AI Accountant Worker

- [ ] Plaid Link integration (OAuth flow)
- [ ] Bank transaction ingest
- [ ] AI Accountant Worker: categorise transactions
- [ ] AI Accountant Worker: match transactions to invoices
- [ ] Reconciliation job: detect drift between Plaid and DB
- [ ] Circuit breaker + retry on all Plaid calls
- [ ] Zero trust: validate all Plaid data before writing to DB

---

## PHASE 5 — Control-Plane Dashboard (Next.js frontend)

- [ ] Overview page: active workers, execution counts, approval queue depth, recent activity
- [ ] Execution log page: all executions with status, confidence, duration; expandable reasoning trace
- [ ] Approval queue page: pending approvals, approve/reject actions, expiry countdown
- [ ] Audit trail page: immutable log, filterable by tenant/worker/date
- [ ] Integrations page: connect/disconnect Xero, QuickBooks, Plaid; show sync status
- [ ] API keys page: generate/revoke tenant API keys
- [ ] All pages read from DB-backed endpoints only — no direct external API calls from UI
- [ ] Design system applied: tokens, typography, motion rules from CLAUDE.md
- [ ] Skeleton loaders (no full-screen spinners)
- [ ] Every execution status change animates (Framer Motion)
- [ ] Worker cards: accent border by status (green/blue/red)

---

## PHASE 6 — Receipt OCR API + Remaining Tools

- [ ] `POST /v1/parse/receipt` — OCR receipt image, extract merchant, amount, date, category
- [ ] Additional standalone API tools (TBD from PRD)
- [ ] All follow same parse → validate → policy → audit → return flow

---

## PHASE 7 — Hardening

- [ ] Rate limiting on all external-facing endpoints
- [ ] Circuit breakers on all integrations (Plaid, Xero, QuickBooks, Stripe)
- [ ] Idempotency keys on all write operations verified end-to-end
- [ ] Sentry wired: all unhandled exceptions captured
- [ ] PostHog wired: agent executions, approval rates, worker usage tracked
- [ ] Reconciliation jobs: detect drift for all integrations
- [ ] Dead-letter queue replay tested
- [ ] Health check endpoints verified: `/health` and `/ready`
- [ ] SOC 2 prep checklist reviewed
- [ ] No financial data in application logs (trace ID correlation only)
- [ ] Webhook signature verification: Stripe, Plaid
- [ ] Load test: agent execution target 2–5 seconds; flag anything above 10s

---

## Mocked / Deferred (track what is not real yet)

| Item | Mocked since | Real in Phase |
|------|-------------|---------------|
| QuickBooks write | Phase 1 | Phase 3 |
| Plaid ingest | — | Phase 4 |
| Xero sync | — | Post-Phase 4 |
| Clerk auth end-to-end | Phase 1 (security.py exists) | Phase 2 |
| RLS policies (DB layer) | Schema ready | Phase 2 |
| BullMQ queue | Phase 1 | Phase 1 |
