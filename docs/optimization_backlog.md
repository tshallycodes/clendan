# Optimization Backlog — Clean / Scalable / Secure / Fast

Tracks the codebase-hardening effort. **Done** items shipped in the optimization pass
(2026-07-06). **TODO** items are written deferrals — audits, load tests, and profiling that
need their own focused effort (and in some cases a running environment).

Priority key: **P0** ship now · **P1** high value, direct · **P2** planned / audit.

---

## Done in this pass

### Clean code
- Removed all remaining backend `TODO`/`FIXME` markers (Codat webhook, OneDrive handler — both
  implemented, not deferred).
- Deleted dead code as part of the AP-first restructure (see `future_expansion.md`).
- Added module/function docstrings to new code (`core/metrics.py`, rate-limiter client reuse,
  worker Sentry init) following PEP 257.
- Naming/idioms: kept to the established conventions (`get_queue_pool` + `enqueue_job`,
  `run_*_job`). **Deliberately avoided sweeping renames** — high diff-noise, low signal.

### Scalability
- **P0 — uniform arq usage.** QuickBooks / Xero / FreshBooks OAuth callbacks were running the
  full multi-minute sync **in the API process** via FastAPI `BackgroundTasks`. All nine call
  sites now `enqueue_job(...)` onto the arq worker. No synchronous in-process background work
  remains (the Mono webhook already enqueued correctly).
- **P1 — rate limiter** reuses a single module-level Redis client + connection pool instead of
  building one per request; hot-path imports moved to module scope (`core/rate_limit.py`).
- **P1 — DB indexes** added for hot query paths: `Execution(tenant_id, created_at)`,
  `Approval(tenant_id, status)`, `AuditLog(tenant_id, created_at)`. Apply with
  `python -m prisma db push`. *Note:* on large tables prefer `CREATE INDEX CONCURRENTLY` to
  avoid a write lock — see P2 below.

### Security
- **Verified** all SQL is parameterized. The only raw SQL is the RLS `set_config('app.
  current_tenant_id', $1, true)` bind-parameter call in `core/db.py`; everything else is Prisma.
- **P0 — Codat webhook** now does real HMAC-SHA256 signature verification against a dedicated
  `codat_webhook_secret` (shipped in the restructure).
- **P1 — `security.txt`** (RFC 9116) added at `frontend/public/.well-known/security.txt`
  (canonical, `clendan.com`) and served from the API host via a `/.well-known/security.txt`
  route.

### Speed / observability
- **P0 — Sentry in the arq worker.** The API had Sentry; the worker did not. `startup()` now
  initialises Sentry when `SENTRY_DSN` is set.
- **P0 — Prometheus.** New `core/metrics.py` with a request counter + latency histogram, wired
  into the HTTP middleware (labelled by **route template**, not raw URL, to avoid cardinality
  blow-up) and exposed at `/metrics`. Degrades to a safe no-op if `prometheus_client` is
  absent, so nothing breaks before `poetry install` picks up the new dep.
- Tests: `tests/test_optimizations.py` covers policy edge cases, autonomy override, dispatch
  mapping integrity, metrics helpers, and the `/metrics` + `security.txt` endpoints (18 tests).

---

## Slow paths identified (not optimized yet)

Instrument these with the new `/metrics` histogram and watch p95 before optimizing.

**API endpoints (latency dominated by Claude / vision):**
- `POST /parse/invoice`, `POST /parse/receipt` — PDF→image + Claude vision (~2–30s).
- Document Intelligence upload — two-pass Claude (classify + extract/analyse).

**Background jobs (arq):**
- Integration initial sync (`sync_quickbooks_connection`, `sync_xero_connection`, …) — many
  sequential external API calls + upserts; the slowest jobs, especially first sync.
- `run_reconciliation_job` — Claude review of unmatched items; minutes for large periods.
- `run_payroll_rec_job`, `run_financial_reporting_job`, `run_payment_run_job`,
  `run_accounts_payable_job` — each makes a Claude call over a batch.

**CPU-bound hotspot:** `_pdf_to_images` (PyMuPDF) renders synchronously inside the async job and
blocks the event loop while rasterising — candidate for `run_in_executor` (see P2).

---

## Written TODOs (deferred — need dedicated effort)

### Scalability — P2
- [ ] **Redis optimizations** — evaluate Lua scripts for the rate-limiter sliding window (one
      atomic round-trip vs a 4-command pipeline) and pipelining opportunities elsewhere.
- [ ] **Integration audit** — per-provider review of rate limits, pagination (are we fetching
      all pages?), and bulk/batch endpoints to cut sync time and API-quota usage.
- [ ] **Load testing** — k6/Locust against `/execute`, `/agents/{id}/run`, and the parse
      endpoints; establish p95/p99 baselines and worker throughput ceilings.
- [ ] **Index rollout** — create the new indexes with `CREATE INDEX CONCURRENTLY` in prod;
      `prisma db push` locks writes while building.

### Security — P2
- [ ] **Input-validation audit** — systematic pass over API bodies, webhook payloads, and
      especially **Anthropic prompt inputs** (prompt-injection from externally-sourced invoice /
      document / bank data flowing into tool prompts). Add allow-listing / escaping where needed.
- [ ] **Crypto audit** — review `integrations/encryption.py` key derivation, per-tenant key
      isolation, and token-at-rest handling.
- [ ] **Penetration test** — external engagement against auth (Clerk JWT), tenant isolation
      (RLS + app layer), and the webhook signature paths.
- [ ] **Dependency vulnerability review** — `pip-audit` / Dependabot in CI; pin and patch.
- [ ] **Threat model** — document trust boundaries (client → API → worker → external
      integrations), data classification, and abuse cases.

### Speed — P2
- [ ] **Profile the worker** — py-spy / cProfile on the arq worker to find the real hotspots in
      sync jobs and Claude pre/post-processing; offload `_pdf_to_images` to a thread pool.
- [ ] **Caching** — evaluate Redis caching (with strict TTL invalidation per CLAUDE.md) for
      tenant config, tool definitions, and policy rules read on every execution.
- [ ] **Queue congestion & retries** — review arq `max_jobs`/concurrency, retry/backoff on
      external calls, and DLQ replay ergonomics under load.
