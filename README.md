# Clendan — AI Financial Agent OS

Autonomous AI tools that process invoices, reconcile accounts, and execute financial tasks under strict policy enforcement with full audit trails.

## Stack

- **Frontend**: Next.js 14 (App Router) + TypeScript + Tailwind + shadcn/ui
- **Backend**: FastAPI (Python 3.12) + Pydantic v2 + Prisma
- **Database**: PostgreSQL with Row-Level Security
- **Auth**: Clerk (server-side JWT verification)
- **AI**: Anthropic SDK (Claude Sonnet — backend only)
- **Queue**: BullMQ + Redis
- **Monitoring**: Sentry + PostHog

## Local Development

### Prerequisites

- Node.js 20+
- Python 3.12+
- Docker & Docker Compose

### Quick Start

1. Copy environment variables:
   ```bash
   cp .env.example .env
   # Fill in required values
   ```

2. Start infrastructure (Postgres + Redis):
   ```bash
   docker-compose up postgres redis -d
   ```

3. Run backend:
   ```bash
   cd backend
   pip install poetry
   poetry install
   poetry run prisma generate
   poetry run prisma db push
   poetry run uvicorn app.main:app --reload
   ```

4. Run frontend:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

### Running Tests

```bash
# Backend
cd backend && python -m pytest

# Frontend
cd frontend && npm test
```

### Full Stack (Docker)

```bash
docker-compose up --build
```

## Environment Variables

See `.env.example` for all required variables.

## Production Deploy (Railway + Vercel)

### 1. Railway — Backend, PostgreSQL, Redis

1. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo
2. Add three services:
   - **PostgreSQL** — Railway template, note the `DATABASE_URL`
   - **Redis** — Railway template, note the `REDIS_URL`
   - **Backend API** — from repo, root directory: `backend/`, uses `railway.toml`
   - **Background Tool** — same repo, root directory: `backend/`, uses `railway.tool.toml`

3. Set env vars on the Backend + Tool services (copy from `.env.example`):
   ```
   DATABASE_URL        (from Railway Postgres)
   REDIS_URL           (from Railway Redis)
   ANTHROPIC_API_KEY
   CLERK_SECRET_KEY
   CLERK_FRONTEND_API
   ENCRYPTION_KEY      (generate: python -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())")
   QUICKBOOKS_CLIENT_ID / QUICKBOOKS_CLIENT_SECRET
   PLAID_CLIENT_ID / PLAID_SECRET
   SENTRY_DSN
   ```

4. First deploy — open the Railway shell on the Backend service and run:
   ```bash
   bash scripts/post_deploy.sh
   ```
   This runs `prisma db push` and applies RLS policies.

5. Note your Railway backend URL (e.g. `https://clendan-api.up.railway.app`)

### 2. Vercel — Frontend

1. Go to [vercel.com](https://vercel.com) → Import Git Repository
2. Set **Root Directory** to `frontend/`
3. Add env vars:
   ```
   NEXT_PUBLIC_API_URL             = https://your-railway-api-url.up.railway.app
   NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
   CLERK_SECRET_KEY
   NEXT_PUBLIC_CLERK_SIGN_IN_URL   = /sign-in
   NEXT_PUBLIC_CLERK_SIGN_UP_URL   = /sign-up
   NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL  = /dashboard
   NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL  = /dashboard
   ```
4. Deploy — Vercel auto-detects Next.js via `vercel.json`

### 3. Update QuickBooks redirect URI

Once Railway is deployed, update `QUICKBOOKS_REDIRECT_URI` to:
```
https://your-railway-api-url.up.railway.app/v1/integrations/quickbooks/callback
```

## Architecture

Master-subagent model: the Financial Orchestrator is the master agent. All tools are sub-agents called as tools. Tools never call each other directly. All coordination and policy enforcement flow through the Orchestrator.

Every agent execution follows: receive → classify → select tool → execute → policy check → output → audit.
