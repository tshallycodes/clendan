# Clendan — Claude Code Configuration

## Project Overview

Clendan is an AI Financial Agent OS. A platform where companies deploy autonomous AI tools
that connect to financial systems, execute tasks, enforce policy, and produce full audit trails.

**Stack:** Next.js 14 (frontend) · FastAPI (backend) · PostgreSQL + Prisma · Clerk (auth) ·
Anthropic SDK · arq + Redis · Vercel + Railway · Sentry + PostHog

**Architecture:** Master-subagent model. Financial Orchestrator is the master agent.
All other tools are sub-agents called as tools. Tools never call each other directly.

---

## Rules
- Use the playwright mcp to help you navigate and understand the codebase
- Do what has been asked; nothing more, nothing less
- NEVER create files unless absolutely necessary — prefer editing existing files
- NEVER create documentation files unless explicitly requested
- ALWAYS read a file before editing it
- NEVER commit secrets, credentials, or .env files
- Keep files under 500 lines — split if exceeded
- If a component exceeds 150 lines, extract sub-components
- Validate input at every system boundary
- When fixing bugs: read only the specific lines needed, not full files
- ALWAYS run database migrations after schema changes
- If an error persists after two attempts, stop and discuss options
- Do not hardcode API keys, secrets, or any credentials, or design styles
- Always pull before pushing your changes to github with

```bash
git pull
git add .
git commit -m "Task title"
git push -u origin main
```

---

## Code Quality

- Delete dead code immediately — unused imports, unreachable branches, commented-out blocks ESPECIALLY after edits
- No tangled dependencies — each module has one clear responsibility
- No duplicated logic — extract shared behaviour into utilities or hooks
- No magic numbers or hardcoded strings — use constants and config
- Every function does one thing
- No `any` types in TypeScript — define proper interfaces for all data
- No raw exception messages to client — always structured error responses
- After every feature addition: audit the file for dead code introduced during development
- Before marking any task complete: check for leftover debug logs, commented code, unused variables

---

## Agent Execution Flow

No agent feature is complete unless it follows every step:

```
receive → classify → select tool → execute → policy check → output → audit
```

### Step Definitions

| Step | Rule |
|------|------|
| Receive | Event or API call arrives at Orchestrator. Input validated before any processing. |
| Classify | Orchestrator identifies event type and determines which tool(s) to invoke. |
| Select Tool | Orchestrator calls the appropriate sub-agent tool as a tool. Never assumed. |
| Execute | Tool runs its task using connected tools (bank API, ERP, OCR, etc). |
| Policy Check | Policy engine validates output before any action is taken. Cannot be skipped. |
| Output | Decision returned with confidence score and full reasoning trace. |
| Audit | Every action written to immutable audit log before returning response to caller. |

### Required Patterns

**Tool invocation:**
```python
# Orchestrator calls tools as tools — never direct execution
result = await orchestrator.invoke_tool(
    tool_type="invoice_processing",
    input=event_payload,
    tenant_id=tenant_id,
    policy_context=policy_rules
)
```

**Retry pattern for external API calls:**
```python
for attempt in range(MAX_ATTEMPTS):
    result = await call_external_api(payload)
    if result.success:
        break
    await asyncio.sleep(BACKOFF_SECONDS * attempt)
else:
    raise ExternalAPIError("Max retries exceeded")
```

**Validation:** All inputs validated with Pydantic before processing. Empty response ≠ success.

**Storage:** `external data → transform → validate → store in DB → expose via API`

### Hard Fail Anti-Patterns

- Tool executing without policy check
- Orchestrator calling tools directly without classifying first
- Single external API call with no retry logic
- Writing to ERP/accounting system before audit log entry
- Agent returning success when external API returned empty
- Skipping the audit step for any reason
- Two tools calling each other directly (bypassing Orchestrator)

**If any step in the agent flow is missing: the feature is incomplete and must not be marked done.**

---

## Financial Data Rules

These rules apply to every feature that touches financial data. No exceptions.

- **ACID guarantees** for all ledger operations — use database transactions
- **Idempotency keys** on all write operations — financial operations must be safe to retry
- **Deterministic currency handling** — never use floating point for currency. Use integer pence/cents internally. Round only at display layer.
- **Audit log immutability** — never UPDATE or DELETE audit rows. Append only.
- **Reconciliation** — every external data sync must have a reconciliation job to detect drift
- **Rollback capability** — any financial action taken by an agent must be reversable where technically possible. Document explicitly where it is not.
- **Zero trust on external data** — data from Plaid, Xero, QuickBooks, Stripe, FreshBooks is always validated before writing to DB. Never pass external data directly to ledger.

---

## Multi-Tenant Rules

Clendan is a multi-tenant platform. Every feature must enforce tenant isolation.

- **Row-level security (RLS)** on every PostgreSQL table — no exceptions
- **Tenant ID on every query** — never query without scoping to tenant
- **Tool credentials isolated per tenant** — API keys for Xero, Plaid, QuickBooks, FreshBooks stored encrypted, scoped to tenant only
- **Agent instances isolated per tenant** — one tenant's tools cannot access another's tools or data
- **Audit logs scoped per tenant** — tenants can only query their own audit trail
- **Cross-tenant data leakage is a critical security failure** — treat it as such

```python
# Every DB query must include tenant scope
result = await db.execute(
    "SELECT * FROM invoices WHERE tenant_id = $1 AND id = $2",
    [tenant_id, invoice_id]
)
```

---

## API Design Rules

- All endpoints versioned: `/v1/...` — never break existing versions
- All financial endpoints require `Idempotency-Key` header
- Rate limiting on every external-facing endpoint
- Webhook endpoints must verify signatures before processing
- Never return raw database errors to API consumers
- Response shape is consistent: `{ data, error, trace_id, timestamp }`

```python
# Standard response shape
return {
    "data": result,
    "error": None,
    "trace_id": correlation_id,
    "timestamp": datetime.utcnow().isoformat()
}
```

---

## Scalable Infrastructure

### Architecture
- Modular boundaries: agents, tools, policy, auth, billing — no cross-domain shortcuts
- Stateless FastAPI services — all state in PostgreSQL or Redis
- Event-driven patterns for agent execution, notifications, audit trails
- arq queues for all async agent jobs — never block request threads with long-running tasks
- Backward-compatible API versioning — v1 never breaks

### Data Layer
- Strong consistency for ledger and audit operations
- Separate read replicas for analytics and reporting queries
- Encryption at rest and in transit
- Field-level encryption for: tenant API keys, financial credentials, PII
- Schema migrations must be zero-downtime — use additive migrations only
- Audit log table: append-only, no UPDATE, no DELETE, no exceptions

### Performance
- Redis cache for tenant config, policy rules, tool definitions — strict TTL invalidation
- Rate limiting and backpressure on all Plaid, Xero, QuickBooks, Stripe API calls
- Batch processing for reconciliation jobs — never run in request thread
- Agent execution target: 2–5 seconds. Flag and investigate anything above 10 seconds.

### Reliability
- Circuit breakers on all external API integrations (Plaid, Xero, QuickBooks, Stripe)
- Retries with exponential backoff and jitter on all external calls
- Dead-letter queues for failed agent jobs — replay without data loss
- Graceful degradation — a failing integration does not stop other tools
- Health check endpoints for all services: `/health` and `/ready`

### Security
- No hardcoded credentials anywhere in the codebase
- All secrets via environment variables only
- Webhook signature verification on all inbound webhooks (Stripe, Plaid, etc.)
- Clerk JWT verified server-side on every protected endpoint — never trust client claims
- Tool credentials (Xero OAuth tokens, Plaid access tokens) encrypted at rest, never logged
- No financial data in application logs — use trace IDs to correlate

### Observability
- Correlation/trace ID on every API request — passed through entire execution chain
- Sentry for error monitoring — all unhandled exceptions captured
- Structured logs only — JSON, never freeform strings
- Audit logs are separate from application logs — different table, different retention
- PostHog for product analytics — track agent executions, approval rates, tool usage

---

## Agent Strategy

Always use parallel subagents for any task involving more than one file or system.

Default pattern:
- Spawn one subagent per file being modified
- Spawn one subagent per FastAPI route being written or read
- Spawn one subagent for schema/migration work, separate from application code
- Spawn one subagent for reading existing code before any writing subagent starts
- Never read and write in the same sequential pass when parallelism is possible
- For phases with multiple components (route + tool + DB migration), always fan out
- When in doubt: more subagents, not fewer

---

## Agent Comms (SendMessage-First Coordination)

Named agents coordinate via SendMessage, not polling or shared state.

```
Lead (you) ←→ researcher ←→ architect ←→ coder ←→ tester ←→ reviewer
```

### Spawning a Coordinated Team

```javascript
// ALL agents in ONE message, each knows WHO to message next
Agent({ prompt: "Research the codebase. SendMessage findings to 'architect'.",
  subagent_type: "researcher", name: "researcher", run_in_background: true })
Agent({ prompt: "Wait for 'researcher'. Design solution. SendMessage to 'coder'.",
  subagent_type: "system-architect", name: "architect", run_in_background: true })
Agent({ prompt: "Wait for 'architect'. Implement it. SendMessage to 'tester'.",
  subagent_type: "coder", name: "coder", run_in_background: true })
Agent({ prompt: "Wait for 'coder'. Write tests. SendMessage results to 'reviewer'.",
  subagent_type: "tester", name: "tester", run_in_background: true })
Agent({ prompt: "Wait for 'tester'. Review code quality and security.",
  subagent_type: "reviewer", name: "reviewer", run_in_background: true })

SendMessage({ to: "researcher", summary: "Start", message: "[task context]" })
```

### Coordination Patterns

| Pattern | Flow | Use When |
|---------|------|----------|
| **Pipeline** | A → B → C → D | Sequential dependencies (feature dev) |
| **Fan-out** | Lead → A, B, C → Lead | Independent parallel work (multiple files) |
| **Supervisor** | Lead ↔ tools | Ongoing coordination (complex refactor) |

### Rules
- ALWAYS name agents — `name: "role"` makes them addressable
- ALWAYS include comms instructions in prompts — who to message, what to send
- Spawn ALL agents in ONE message with `run_in_background: true`
- After spawning: STOP, tell user what's running, wait for results
- NEVER poll status — agents message back or complete automatically

### When to Use Subagents

| Use | Don't Use |
|-----|-----------|
| 3+ files touched | Single file edits |
| New agent tools | 1–2 line fixes |
| Cross-module changes | Config changes |
| New FastAPI routes | Documentation updates |
| New integrations (Plaid, Xero) | Simple questions |
| DB schema changes | Minor UI tweaks |

### Agent Types

**Core**: `coder`, `reviewer`, `tester`, `planner`, `researcher`
**Architecture**: `system-architect`, `backend-dev`, `frontend-dev`
**Security**: `security-architect`, `security-auditor`
**Finance**: `financial-logic-reviewer` — use for any agent that touches ledger, policy, or audit

---

## Build & Test

```bash
# Frontend
cd frontend && npm run build && npm test

# Backend API
cd backend && pytest && uvicorn app.main:app --reload

# Background tool
cd backend && python run_tool.py app.tool.ToolSettings

# Full stack
docker-compose up --build
```

- ALWAYS run tests after code changes
- ALWAYS verify build succeeds before committing
- Financial logic requires unit tests — policy engine, currency rounding, audit writing
- Integration tests required for: Plaid connection, Xero sync, agent execution chain

---

## Design System

### Theme Architecture

The app uses **light mode by default**. Dark mode activates via the `.dark` class on `<html>`.
All colors are CSS variables defined in `globals.css` — never hardcode hex values in components.
Always use Tailwind design token classes (`bg-brand-surface`, `text-brand-text`, etc.).

### Brand Color Tokens

| Tailwind Class | Light value | Dark value | Usage |
| -------------- | ----------- | ---------- | ----- |
| `bg-brand-bg` / `text-brand-bg` | `#f5f5f5` | `#0a0a0a` | Page background |
| `bg-brand-surface` | `#ffffff` | `#111111` | Cards, panels, drawers, sidebars |
| `bg-brand-elevated` | `#f0f0f0` | `#1a1a1a` | Modals, dropdowns, nested cards |
| `border-brand-border` / `divide-brand-border` | `#e0e0e0` | `#2c2c2c` | Card borders, dividers |
| `border-brand-border-subtle` | `#ebebeb` | `#222222` | Subtle separators |
| `text-brand-text` | `#111111` | `#f0f0f0` | Primary text |
| `text-brand-secondary` | `#444444` | `#a0a0a0` | Labels, metadata |
| `text-brand-muted` | `#888888` | `#666666` | Timestamps, captions, placeholders |

**Hard rule: never write raw hex values for any of the above.** Use the Tailwind token class.
Inline styles are allowed only for dynamic values (e.g. computed chart colours, bank brand colours).

### Semantic Colors — Same in Both Modes

These never change between light and dark. Use raw hex or `brand-*` token:

| Token | Value | Usage |
| ----- | ----- | ----- |
| `bg-brand-green` / `#00C853` | Electric Green | Primary CTA, success states — see strict rules below |
| `#ff4d6d` | Danger red | Blocked actions, fraud flags, policy violations |
| `rgba(255,77,109,0.08)` | Danger tint | Danger card backgrounds |
| `#00a8cc` | Info blue | Approval-required states, neutral info |
| `#f5a623` | Warning amber | Stale data, slow execution, pending states |
| `rgba(0,0,0,0.7)` | Overlay | Modal backdrops |

### Electric Green Rules — STRICT

Electric Green `#00C853` appears ONLY on:

- Logo mark
- Primary CTA button (one per page/screen max)
- Active nav indicator (dot or underline only — NOT the icon itself)
- Successful execution status indicators
- Positive financial values and auto-approved states
- Tool active/running pulse indicators
- Toggle switches (on state)
- Input focus border (`1px solid #00C853`)
- Chart lines showing positive trends
- Confidence score bars above 0.9

Electric Green NEVER appears on:

- Nav icons — use `text-brand-muted` inactive, `text-brand-text` active
- Card borders or dividers — use `border-brand-border`
- Secondary buttons — use `border-brand-border` outline only
- Page titles and section headers
- Badges and status tags (use semantic colors)
- Background fills or decorative elements
- Anything that does not represent a successful or positive execution outcome

**The dashboard reads as monochrome. Green appears only where execution succeeds.**

### Tool Status Colors

| Status | Color | Usage |
|--------|-------|-------|
| Running / Auto-executed | `#00C853` | Active tool indicators, success states |
| Approval Required | `#00a8cc` | Pending human review |
| Blocked / Flagged | `#ff4d6d` | Policy violation, fraud flag, escalated |
| Inactive / Disabled | `text-brand-muted` | Tool turned off, not yet deployed |

Never repurpose status colors outside tool/execution display.

### Typography Scale

| Style | Size | Weight | Font | Usage |
|-------|------|--------|------|-------|
| H1 | 48px | 800 | Syne | Hero headlines |
| H2 | 32px | 700 | Syne | Page titles |
| H3 | 22px | 700 | Syne | Section headers |
| H4 | 16px | 600 | Syne | Card titles |
| Body | 14px | 400 | IBM Plex Mono | General content |
| Body-small | 12px | 400 | IBM Plex Mono | Secondary content |
| Caption | 11px | 400 | IBM Plex Mono | Timestamps, footnotes |
| Label | 10px | 500 | IBM Plex Mono | Uppercase section labels |
| Code | 12px | 400 | IBM Plex Mono | API endpoints, trace IDs, JSON |

Financial values: `text-brand-text` neutral · `#00C853` auto-approved · `#ff4d6d` blocked. Labels never green.

### Spacing — 8pt Grid

`xs: 4px` / `sm: 8px` / `md: 16px` / `lg: 24px` / `xl: 32px` / `xxl: 48px`

Page container padding: `lg` or `xl`. Data clusters: `xs` or `sm`. Card internal padding: `md`.

### Border Radius

`xs: 2px` / `sm: 4px` / `md: 6px` / `lg: 8px` / `full: 9999px`

Clendan is sharp-edged — infrastructure product aesthetic. Default: `sm`. Max: `md`. No soft rounded cards.

### Component Patterns

**Primary Button:** `bg-[#00C853] text-black hover:bg-[#00a844] active:scale-[0.97]`. One per page.

**Secondary Button:** `bg-transparent border border-brand-border text-brand-text hover:bg-brand-elevated`.

**Danger Button:** `bg-[rgba(255,77,109,0.1)] border border-[#ff4d6d] text-[#ff4d6d]`. Block/reject actions only.

**Cards:** `bg-brand-surface border border-brand-border rounded-sm p-4`. No shadows — flat is correct.

**Inputs:** `bg-brand-bg border border-brand-border focus:border-[#00C853] text-brand-text placeholder:text-brand-muted rounded-sm`.

**Status Badge:**

- Auto: `bg-[rgba(0,200,83,0.08)] text-[#00C853] border border-[rgba(0,200,83,0.2)]`
- Pending: `bg-[rgba(0,168,204,0.08)] text-[#00a8cc] border border-[rgba(0,168,204,0.2)]`
- Blocked: `bg-[rgba(255,77,109,0.08)] text-[#ff4d6d] border border-[rgba(255,77,109,0.2)]`

**API Code Block:** `bg-brand-bg border border-brand-border` font IBM Plex Mono 12px. Keywords: `#f5a623`. Strings: `#00C853`. Comments: `text-brand-muted`. Copy button top-right.

**Audit Trail Row:** `bg-brand-surface hover:bg-brand-elevated`, expandable. Expanded state shows full reasoning trace in monospace. Trace IDs in `text-brand-muted`.

**Tool Card:** `bg-brand-surface border border-brand-border`. Active: `border-l-[3px] border-l-[#00C853]`. Approval-required: `border-l-[3px] border-l-[#00a8cc]`. Blocked: `border-l-[3px] border-l-[#ff4d6d]`. Inactive: no accent border.

### Motion Rules

- Every execution status change animates — no instant state jumps
- Animation only for state changes, never decorative
- Animation stops immediately on error
- Use Framer Motion for all Next.js animations
- Skeleton loaders only — no full-screen spinners
- Every button: idle → hover → active (scale 0.97) → loading → success/error
- Execution log lines animate in sequentially — 150ms stagger per line
- Tool status changes: fade + slight translate, 200ms ease
- Charts animate on load and between time ranges — static charts are not acceptable
- Approval queue counter changes: number interpolates, never jumps

**Motion Anti-Patterns (Hard Fail):**
- Execution status updating without visual transition
- Decorative animation unrelated to state change
- Success state shown before backend confirmation received
- Full-screen loading blocks
- Charts without hover/scrub interaction
- Buttons missing loading or error state
- Audit log updating silently without any indication

---

## Clendan-Specific Rules

- All Anthropic API calls via FastAPI backend — never from Next.js client directly
- Tool execution always goes through arq queue — never block API request threads
- Policy engine runs on every agent output before any action is taken — cannot be bypassed
- Audit log written before returning response — if audit write fails, the operation fails
- Tenant isolation enforced at DB layer (RLS) AND application layer — both required
- Tool credentials (Xero OAuth, Plaid tokens, FreshBooks OAuth) encrypted with tenant-specific keys — never logged
- Agent reasoning traces stored in full — never truncate reasoning for storage savings
- Completed tasks: move to done.md, never delete — audit trail for development
- Every 10 Claude Code tasks ≈ 5% weekly limit — be surgical with file reads
- Currency: store as integer (pence/cents), convert to decimal at display layer only
- Tool versioning: every tool has a version field — agent decisions log the version used
- Human approval API: approval expiry must be enforced — stale approvals rejected after configured TTL
- Clerk auth: verify JWT server-side on every protected FastAPI route — `requireAuth()` in middleware
- Never expose raw Plaid, Xero, QuickBooks, or FreshBooks error messages to the frontend — map to structured errors
- Integration connection flow: OAuth → callback → store encrypted token → trigger initial sync → poll → confirm data present → mark connected. All steps required.
- `POST /v1/agents/{id}/run` is idempotent — same idempotency key must return same result
- Dashboard reads from DB-backed endpoints only — never calls external APIs directly from UI