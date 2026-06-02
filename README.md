# Clendan — AI Financial Agent OS

Autonomous AI workers that process invoices, reconcile accounts, and execute financial tasks under strict policy enforcement with full audit trails.

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

## Architecture

Master-subagent model: the Financial Orchestrator is the master agent. All workers are sub-agents called as tools. Workers never call each other directly. All coordination and policy enforcement flow through the Orchestrator.

Every agent execution follows: receive → classify → select worker → execute → policy check → output → audit.
