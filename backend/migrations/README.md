# Database Migrations

These are raw SQL migrations applied outside of Prisma (for operations Prisma cannot handle, like RLS policies).

## How to apply

```bash
# Apply all migrations in order
psql $DATABASE_URL -f migrations/001_enable_rls.sql
```

## 001_enable_rls.sql

Enables PostgreSQL Row-Level Security on all tables. Every query must set `app.current_tenant_id` before executing:

```sql
SET LOCAL app.current_tenant_id = '<tenant_id>';
SELECT * FROM "Invoice"; -- only returns rows for that tenant
```

The application sets this via `tenant_context()` in `app/core/db.py`.
