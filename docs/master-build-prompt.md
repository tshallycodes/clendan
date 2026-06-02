# Clendan — Master Build Prompt (Claude Code)

> Paste this as your first message in Claude Code, in the empty `clendan/` repo,
> with `CLAUDE.md` already in the root. This prompt sets up the foundation and
> builds Phase 1 only. Do not ask Claude Code to build everything at once —
> follow the phase plan at the bottom, one phase per session, verifying each.

---

## Read First

You are building Clendan, an AI Financial Agent OS — API-first execution
infrastructure where companies deploy autonomous AI workers that process
invoices, reconcile accounts, and execute financial tasks under strict policy,
with a full audit trail on every action.

Before writing any code:
1. Read `CLAUDE.md` in the repo root in full. Every rule in it is binding.
2. Read this entire prompt including the phase plan before starting.
3. Do not begin Phase 1 until you have confirmed the foundation setup below.

The architecture is master-subagent: a Financial Orchestrator is the master
agent; all workers are sub-agents it calls as tools. Workers never call each
other directly. All coordination and all policy enforcement flow through the
Orchestrator. The MVP wedge is invoice processing.

---

## Stack (do not deviate without asking)

- Frontend: Next.js 14 (App Router) + TypeScript + Tailwind + shadcn/ui
- Backend: FastAPI (Python 3.12) + Pydantic v2
- Database: PostgreSQL + Prisma (via `prisma-client-py`) — row-level security on every table
- Auth: Clerk (verified server-side on every protected route)
- AI: Anthropic SDK (Claude Sonnet) — backend only, never called from the client
- Queue: BullMQ + Redis for all async agent jobs
- Hosting target: Vercel (frontend) + Railway (backend, Postgres, Redis)
- Monitoring: Sentry + PostHog

---

## Repo Structure to Create

```
clendan/
├── CLAUDE.md                 # already present — read it
├── README.md                 # how to run locally + env vars
├── docker-compose.yml        # postgres + redis + backend for local dev
├── .env.example              # committed, no real values
├── .gitignore                # must ignore .env, __pycache__, node_modules, .next
├── frontend/                 # Next.js 14
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── ...
└── backend/                  # FastAPI
    ├── app/
    │   ├── main.py
    │   ├── core/             # config, security, db, logging
    │   ├── api/v1/           # versioned routes
    │   ├── workers/          # agent sub-agents
    │   ├── orchestrator/     # master agent
    │   ├── policy/           # policy engine
    │   ├── audit/            # immutable audit logging
    │   ├── integrations/     # plaid, quickbooks adapters
    │   └── models/           # pydantic + prisma models
    ├── prisma/
    │   └── schema.prisma
    ├── tests/
    └── pyproject.toml
```

---

## FOUNDATION (do this first, then STOP and report before Phase 1)

1. Scaffold the repo structure above.
2. Create `frontend/` with `create-next-app` (TypeScript, Tailwind, App Router).
3. Create `backend/` FastAPI skeleton with:
   - `core/config.py` — settings from env vars only (Pydantic Settings)
   - `core/db.py` — Prisma client init
   - `core/security.py` — Clerk JWT verification middleware (`require_auth`)
   - `core/logging.py` — structured JSON logging with correlation/trace IDs
   - `main.py` — app factory, CORS, Sentry init, `/health` and `/ready` endpoints
   - Standard response shape on every endpoint: `{ data, error, trace_id, timestamp }`
4. Write `prisma/schema.prisma` with these initial models — every table has
   `tenant_id` and RLS in mind:
   - `Tenant` (id, name, created_at)
   - `User` (id, tenant_id, clerk_user_id, email, role)
   - `Integration` (id, tenant_id, type [xero|quickbooks|plaid], encrypted_credentials, status, connected_at)
   - `Worker` (id, tenant_id, type, config_json, autonomy_level [auto|approve|suggest], version, status)
   - `Execution` (id, tenant_id, worker_id, input_ref, decision, confidence, status [auto|pending|blocked], duration_ms, created_at)
   - `Approval` (id, tenant_id, execution_id, status, requested_at, responded_at, responder_id, expires_at)
   - `AuditLog` (id, tenant_id, execution_id, actor, action, reasoning_trace_json, model_version, created_at) — APPEND ONLY, never updated or deleted
   - `Invoice` (id, tenant_id, vendor, invoice_number, amount_minor [integer pence], currency, due_date, status, raw_document_ref, parsed_json, created_at)
5. Write `docker-compose.yml` for local Postgres + Redis + backend.
6. Write `.env.example` listing every required variable (no values).
7. Write `README.md` with local run instructions.
8. Set up `pytest` and a Next.js test runner. Add a trivial passing test on each
   side to confirm the harness works.

Then run the build/test commands from `CLAUDE.md`, confirm both sides build and
the trivial tests pass, and STOP. Report what was created and confirm the
foundation is green before moving to Phase 1.

---

## PHASE 1 — Invoice Parser API + Invoice Processing Worker (MVP core)

Only start after the foundation is confirmed green.

Goal: a working end-to-end loop where an invoice document is parsed, validated,
policy-checked, and either auto-approved, routed for approval, or blocked — with
a full immutable audit entry for every outcome. No real external integrations
yet; mock the QuickBooks write behind an interface so it can be swapped later.

Build, in this order, using parallel subagents per `CLAUDE.md` (reader subagent
first, then architect, then coders per module, then tester, then reviewer):

1. **Invoice Parser API** — `POST /v1/parse/invoice`
   - Accepts PDF/PNG/JPG upload
   - Calls Claude (Anthropic SDK) to extract: vendor, invoice_number, line_items,
     amount_minor (integer), currency, due_date, vat, po_number, confidence
   - Returns the standard response shape
   - Validates output with Pydantic before returning; empty/low-confidence is not success
   - Idempotency-Key header supported

2. **Policy Engine** — `app/policy/`
   - Deterministic rules evaluated on every worker output
   - MVP rules: amount thresholds (auto under X, approve X–Y, block above Y),
     verified-supplier check, currency allow-list
   - Pure functions, fully unit-tested, no side effects
   - Same input always produces same decision

3. **Audit Logger** — `app/audit/`
   - Append-only writes to `AuditLog`
   - Writes the full reasoning trace, never truncated
   - If the audit write fails, the whole operation fails (no silent success)

4. **Invoice Processing Worker** — `app/workers/invoice_processing.py`
   - A sub-agent with a clear interface (so the Orchestrator can call it as a tool later)
   - Flow: parse → validate against tenant supplier list → policy check →
     decision (auto/approve/block) → write to accounting (mocked interface) →
     audit → return
   - Currency handled as integer minor units throughout; format only at edges

5. **Execution + Approval APIs**
   - `POST /v1/agents/{worker_id}/run` — idempotent; runs the worker, returns decision
   - `POST /v1/approvals/{id}/respond` — approve/reject; enforces approval expiry (TTL)
   - All scoped to tenant; RLS enforced at DB layer AND tenant check at app layer

6. **Queue wiring**
   - Worker execution runs through BullMQ/Redis, not in the request thread
   - Dead-letter handling for failed jobs

7. **Tests**
   - Unit tests: policy engine (all branches), currency rounding, audit append
   - Integration test: full execution chain for each of the three outcomes
     (auto-approved, approval-required, blocked)
   - A blocked-policy case must prove no accounting write occurred

Then run build + tests, confirm green, and STOP. Report results and list exactly
what was built and what is mocked.

---

## Phase Plan (for context — build ONE per session, do not jump ahead)

- **Phase 1** — Invoice Parser API + Invoice Processing Worker + Policy + Audit (above)
- **Phase 2** — Clerk auth wired end-to-end; tenant onboarding; RLS verified with a
  cross-tenant isolation test that must fail to read another tenant's data
- **Phase 3** — Real QuickBooks integration behind the mocked interface (OAuth →
  callback → encrypted token store → initial sync → poll → confirm → mark connected)
- **Phase 4** — Plaid integration + AI Accountant Worker (bank txn ingest, categorise, match)
- **Phase 5** — Control-plane dashboard (Next.js): overview, execution log, approval
  queue, audit trail, integrations, API keys — reads only from DB-backed endpoints
- **Phase 6** — Receipt OCR API + remaining standalone API tools
- **Phase 7** — Hardening: rate limiting, circuit breakers, idempotency everywhere,
  Sentry/PostHog wired, reconciliation jobs, SOC 2 prep checklist

---

## Non-Negotiables (from CLAUDE.md — restated because they matter most here)

- Policy engine runs on every agent output before any action — never bypassed
- Audit log written before the response returns — audit failure = operation failure
- Currency stored as integer minor units — never floating point
- Tenant isolation at DB (RLS) AND app layer — both required
- Anthropic calls from backend only — never the client
- Tool credentials encrypted at rest, never logged
- No `any` types; no hardcoded secrets; structured errors only
- Files under 500 lines; functions do one thing
- Run tests after changes; verify build before reporting done

---

## How to Work

- Use parallel named subagents for any multi-file step (reader → architect →
  coders → tester → reviewer), coordinating via SendMessage per CLAUDE.md.
- Read before you write. Never read and write in the same sequential pass when
  parallelism is possible.
- If an error persists after two attempts, STOP and discuss options — do not
  thrash or hack around financial-logic correctness.
- After each phase: report what was built, what is mocked, test results, and the
  exact next step. Then wait.

Begin with the FOUNDATION now. Do not start Phase 1 until the foundation is
confirmed green and you have reported back.
