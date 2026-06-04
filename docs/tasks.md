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

## PHASE 1 — Invoice Parser + Policy + Audit + Worker ✅ COMPLETE (2026-06-04)

### 1.1 Invoice Parser API — `POST /v1/parse/invoice`
- [x] Accept PDF/PNG/JPG upload (PyMuPDF converts PDF pages → PNG → Claude vision)
- [x] Call Claude (Anthropic SDK) to extract: vendor, invoice_number, line_items, amount_minor (integer), currency, due_date, vat, po_number, confidence
- [x] Pydantic output model — validate before returning; empty/low-confidence is not success
- [x] Idempotency-Key header support (Redis cache, 24h TTL)
- [x] Standard response shape: `{ data, error, trace_id, timestamp }`

### 1.2 Policy Engine — `app/policy/engine.py`
- [x] Deterministic rule evaluation on every worker output
- [x] Rule: amount threshold — auto under X, approve X–Y, block above Y
- [x] Rule: verified-supplier check
- [x] Rule: currency allow-list
- [x] Pure functions, no side effects
- [x] Full unit test coverage of all branches

### 1.3 Audit Logger — `app/audit/logger.py`
- [x] Append-only writes to AuditLog table
- [x] Full reasoning trace stored, never truncated
- [x] If audit write fails → operation fails (no silent success)
- [x] Unit tests: confirm append-only behaviour

### 1.4 Invoice Processing Worker — `app/workers/invoice_processing.py`
- [x] Clear interface callable by Orchestrator as a tool
- [x] Flow: parse → policy check → audit (FIRST) → accounting write → return
- [x] Currency as integer minor units throughout; format only at display edge
- [x] Three outcomes: auto-approved, approval-required, blocked

### 1.5 Execution API — `POST /v1/agents/{worker_id}/run`
- [x] Idempotent — same idempotency key returns same result (stored in input_ref)
- [x] Runs worker through arq + Redis queue (not in request thread)
- [x] Scoped to tenant; enforced at application layer (DB-layer RLS: Phase 2)
- [x] Standard response shape

### 1.6 Approval API — `POST /v1/approvals/{id}/respond`
- [x] Approve / reject actions
- [x] Enforces approval expiry TTL — stale approvals rejected (HTTP 410)
- [x] Scoped to tenant

### 1.7 Queue Wiring
- [x] arq + Redis integration — `run_invoice_job` registered in `app/worker.py`
- [x] Worker execution runs via queue, not in request thread
- [x] Dead-letter queue for failed jobs (Redis RPUSH to `clendan:dlq` via `app/queue/pool.py`)

### 1.8 Tests
- [x] Unit: policy engine — all branches (auto / approve / block) — `tests/test_policy.py`
- [x] Unit: currency rounding — `tests/test_currency.py`
- [x] Unit: audit append behaviour — `tests/test_audit.py`
- [x] Integration: auto-approved execution end-to-end
- [x] Integration: approval-required execution end-to-end
- [x] Integration: blocked execution end-to-end
- [x] Proof: blocked case → no accounting write occurred

### Notes
- Queue: arq (Python async Redis queue — BullMQ equivalent for FastAPI/asyncio)
- PDF: PyMuPDF (pages → PNG → Claude vision API)
- Accounting write mocked; Phase 3 swaps in real QuickBooks client
- Clerk auth deferred to Phase 2; Phase 1 uses `X-Tenant-ID` header

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

## PHASE 3 — QuickBooks Integration ✅ COMPLETE (2026-06-03)

- [x] `app/core/encryption.py` — Fernet encrypt/decrypt; dev key warning; never logs plaintext
- [x] `app/integrations/quickbooks/circuit_breaker.py` — CLOSED/OPEN/HALF_OPEN state machine (5 failures → open, 60s recovery)
- [x] `app/integrations/quickbooks/client.py` — OAuth2 client: `build_auth_url`, `exchange_code`, `refresh_token`, `get_company_info`, `revoke_token`; all tokens encrypted at rest; 3-attempt retry with exponential backoff + jitter; raw QB errors never exposed
- [x] `app/integrations/quickbooks/sync.py` — arq job: verifies live connection, falls back to token refresh, marks error if both fail; tenant isolation enforced before credential access
- [x] `app/worker.py` — arq `WorkerSettings`: registers sync job, wires Redis, DB lifecycle
- [x] `GET /v1/integrations/quickbooks/connect` — returns OAuth authorization URL
- [x] `GET /v1/integrations/quickbooks/callback` — exchanges code, stores encrypted tokens, verifies connection via company info fetch, marks connected
- [x] `GET /v1/integrations/quickbooks/status` — returns connection status
- [x] `DELETE /v1/integrations/quickbooks/disconnect` — revokes tokens, marks disconnected
- [x] All routes scoped to tenant via clerk_user_id lookup
- [x] `pyproject.toml` — `arq = "^0.25.0"` added
- [x] `config.py` — QB client_id, client_secret, redirect_uri, sandbox flag
- [x] `.env.example` — QB env vars documented

- [ ] **Swap mock accounting write** (Phase 1) → real QB client — deferred until Ryan completes Phase 1 mock interface
- [ ] Full OAuth flow test with real QB sandbox credentials (requires `QUICKBOOKS_CLIENT_ID` + `QUICKBOOKS_CLIENT_SECRET`)

**Tests: 12 passed, 1 skipped — no regressions**

---

## PHASE 4 — Plaid Integration + AI Accountant Worker ✅ COMPLETE (2026-06-03)

### Schema
- [x] `BankAccount` model — tenant-scoped, `plaid_account_id` unique, `current_balance_minor` Int
- [x] `BankTransaction` model — `amount_minor` Int (never float), `plaid_transaction_id` unique, `ai_category`, `matched_invoice_id`, status
- [x] RLS policies added for both new tables in `migrations/001_enable_rls.sql`
- [x] Prisma client regenerated

### Plaid Integration
- [x] `app/integrations/plaid/client.py` — `create_link_token`, `exchange_public_token`, `get_accounts`, `sync_transactions`, `plaid_amount_to_minor` (float → integer cents); all calls through circuit breaker + 3-attempt retry with jitter; access token encrypted at rest
- [x] `app/integrations/plaid/circuit_breaker.py` — reuses QuickBooks circuit breaker, named `"plaid"`
- [x] `app/integrations/plaid/sync.py` — `sync_plaid_transactions` (cursor-based pagination, account upsert, transaction ingest, cursor persistence); `reconcile_plaid_transactions` (drift detection, auto re-sync); `enqueue_plaid_sync`

### Plaid API Routes
- [x] `POST /v1/integrations/plaid/link-token` — creates Plaid Link token
- [x] `POST /v1/integrations/plaid/exchange-token` — exchanges public_token, stores encrypted creds, triggers sync
- [x] `GET /v1/integrations/plaid/status` — connection status + account/transaction counts
- [x] `GET /v1/integrations/plaid/transactions` — paginated tenant-scoped transaction list
- [x] `DELETE /v1/integrations/plaid/disconnect` — wipes credentials, marks disconnected

### AI Accountant Worker
- [x] `app/workers/ai_accountant.py` — full 7-step execution flow (receive → classify → execute → policy check → output → execution record → audit)
- [x] Claude `claude-sonnet-4-6` categorises transactions + matches to invoices in one call
- [x] Policy check: category allow-list, confidence thresholds (auto ≥0.85, approve ≥0.50, block <0.50)
- [x] Blocked decisions: no DB writes to transactions
- [x] Writes `Execution` + `AuditLog` records with full reasoning trace
- [x] `run_ai_accountant` arq job wrapper registered in `app/worker.py`

### Config + env
- [x] `config.py` — `plaid_client_id`, `plaid_secret`, `plaid_env`
- [x] `.env.example` — Plaid vars documented

**Tests: 12 passed, 1 skipped — no regressions**

**To go live:** Add `PLAID_CLIENT_ID` + `PLAID_SECRET` from [dashboard.plaid.com](https://dashboard.plaid.com) and set `PLAID_ENV=sandbox`

---

## PHASE 5 — Control-Plane Dashboard (Next.js frontend) ✅ COMPLETE (2026-06-04)

### Design system
- [x] `globals.css` — Tailwind v4 `@theme inline` with all `--color-brand-*` tokens
- [x] `layout.tsx` — Syne (headings) + IBM Plex Mono (body) via `next/font/google`
- [x] Dark background `#0a0a0f`, Surface `#111118`, Electric green `#00C853` on success only
- [x] `framer-motion` installed (ready for animated state transitions)
- [x] `lib/utils.ts` — `cn()`, `formatCurrency()`, `formatDate()`, `formatTime()`

### Backend read endpoints (`app/api/v1/dashboard.py`)
- [x] `GET /v1/dashboard/stats` — executions, pending approvals, active workers, invoices, transactions
- [x] `GET /v1/dashboard/executions` — paginated, newest first, worker type included
- [x] `GET /v1/dashboard/approvals` — pending only, oldest first, confidence + decision included
- [x] `GET /v1/dashboard/audit` — immutable read, newest first
- [x] `GET /v1/dashboard/workers` — all workers for tenant

### Frontend pages (all server components, data from DB-backed endpoints only)
- [x] `app/(dashboard)/layout.tsx` — sticky sidebar + auth guard + dark shell
- [x] `app/(dashboard)/page.tsx` — Overview: 4 stat cards (animated count-up) + active workers
- [x] `app/(dashboard)/executions/page.tsx` — execution log table with status badges
- [x] `app/(dashboard)/approvals/page.tsx` — approval queue with urgency accent + approve/reject actions
- [x] `app/(dashboard)/audit/page.tsx` — immutable audit trail with actor/action/timestamp
- [x] `app/(dashboard)/integrations/page.tsx` — QB + Plaid connection status cards

### Shared components
- [x] `components/dashboard/Sidebar.tsx` — sticky nav, green active indicator, correct icon colors
- [x] `components/dashboard/StatusBadge.tsx` — 8 states, all with correct semantic colors
- [x] `components/dashboard/StatCard.tsx` — animated count-up via `requestAnimationFrame`
- [x] `components/dashboard/Skeleton.tsx` — `TableSkeleton` for loading states (no spinners)
- [x] `components/dashboard/ApproveActions.tsx` — client component, POST → `router.refresh()`
- [x] `lib/api.ts` — `apiGet<T>()` / `apiPost<T>()` with auth headers

### Tests + verification
- [x] Backend: **12 passed, 1 skipped**
- [x] Frontend: **1/1 Vitest**, TypeScript clean
- [x] Playwright: dark `#0a0a0f` background ✅ · IBM Plex Mono font ✅ · `/dashboard` → 307 redirect ✅ · sign-in renders correctly ✅

### Deferred
- [ ] API keys page (Phase 6+)
- [ ] Framer Motion execution status animations (wired up once Phase 1 execution flow is live)
- [ ] Worker cards with accent borders (needs workers in DB — deploy Phase 1 first)

---

## PHASE 6 — Receipt OCR API + Remaining Tools ✅ COMPLETE (2026-06-04)

- [x] `POST /v1/parse/receipt` — Claude vision extracts merchant, amount_minor, currency, date, category
- [x] `app/models/receipt_parse.py` — ParsedReceipt Pydantic model; unknown category coerced to "other"
- [x] `app/workers/receipt_processing.py` — full flow: parse → policy (category allow-list) → audit → return
- [x] `run_receipt_job` registered in `app/worker.py`
- [x] Idempotency-Key support (Redis cache, 24h TTL) on parse route
- [x] `tests/test_receipt.py` — 6 tests: auto-approved, blocked category, audit written, low-confidence raises

---

## PHASE 8 — Railway + Vercel Production Setup ✅ CONFIG COMPLETE (2026-06-04)

### Config files created (commit and push — Railway/Vercel pick these up automatically)
- [x] `backend/railway.toml` — web service: Dockerfile build, `uvicorn` on `$PORT`, `/health` healthcheck
- [x] `backend/railway.worker.toml` — worker service: same Dockerfile, `python -m arq app.worker.WorkerSettings`
- [x] `backend/Dockerfile` — CMD updated to use `${PORT:-8000}` for Railway compatibility
- [x] `backend/scripts/post_deploy.sh` — runs `prisma db push` + RLS migration after first deploy
- [x] `frontend/vercel.json` — Next.js framework declaration, root `.next` output
- [x] `README.md` — full step-by-step Railway + Vercel deploy guide

### Manual steps (requires Railway + Vercel accounts)
- [ ] Create Railway project → add PostgreSQL + Redis + Backend API + Background Worker services
- [ ] Set all env vars from `.env.example` on Railway services (see README for full list)
- [ ] First deploy: open Railway shell → `bash scripts/post_deploy.sh` (schema + RLS)
- [ ] Note Railway backend URL → set as `NEXT_PUBLIC_API_URL` in Vercel env vars
- [ ] Import frontend repo on Vercel, set root directory to `frontend/`, add env vars
- [ ] Update `QUICKBOOKS_REDIRECT_URI` to Railway URL once deployed
- [ ] Verify `https://your-api.railway.app/health` returns 200

### Phase 1 review note (for Ryan)
- `parse/invoice.py` calls Claude synchronously in the request thread — should enqueue to arq like `agents/run.py` does

---

## PHASE 7 — Hardening ✅ COMPLETE (2026-06-04)

- [x] **Rate limiting** — `app/core/rate_limit.py` sliding-window middleware: 20/min parse, 30/min agents, 200/min general; Redis-backed; returns 429 + Retry-After; never blocks on Redis failure
- [x] **Circuit breakers** — QB (Phase 3) + Plaid (Phase 4) already have `CircuitBreaker` state machines; Xero/Stripe not yet integrated
- [x] **Idempotency keys** — verified on parse/invoice, parse/receipt, agents/run; approvals inherently idempotent
- [x] **Sentry** — initialized at startup via `lifespan`; captures all unhandled exceptions (foundation)
- [x] **PostHog** — `app/core/analytics.py`; `track_execution`, `track_approval`, `track_worker_status`; no-op when key not set; no financial amounts in events
- [x] **Reconciliation** — Plaid `reconcile_plaid_transactions` arq job (Phase 4); QB sync job (Phase 3)
- [x] **DLQ replay** — `GET /v1/dlq`, `POST /v1/dlq/replay/{job_id}`, `DELETE /v1/dlq/flush`
- [x] **Health checks** — `/health` (ok), `/ready` now checks DB (`SELECT 1`) + Redis (`PING`) and returns `"degraded"` if either fails
- [x] **No financial data in logs** — removed `amount_minor`/`currency` from `_mock_accounting_write` log; trace IDs used for correlation
- [x] **Plaid webhook** — `POST /v1/webhooks/plaid`; JWT signature verification via Plaid JWKS; 5-minute freshness window; enqueues transaction sync on TRANSACTIONS events
- [x] **Load test target** — execution target 2–5s; anything above 10s should be investigated (arq job timeout = 300s)
- [x] `tests/test_hardening.py` — 8 tests: rate limit paths, webhook token expiry/missing-kid/valid, DLQ list/replay, analytics no-op

### Still required before production
- [ ] Set `POSTHOG_API_KEY` to enable analytics
- [ ] Set `PLAID_WEBHOOK_SECRET` (used for future HMAC fallback if needed)
- [ ] Stripe webhook verification (once Stripe integration is added)
- [ ] Run actual load test against Railway deployment

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
