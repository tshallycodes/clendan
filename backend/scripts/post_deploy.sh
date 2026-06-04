#!/bin/bash
# Run this once after first Railway deploy (via Railway shell or as a one-off command).
# DATABASE_URL must be set in environment.
set -e

echo "==> Generating Prisma client..."
prisma generate

echo "==> Pushing schema to database..."
prisma db push --skip-generate

echo "==> Applying RLS policies..."
psql "$DATABASE_URL" -f migrations/001_enable_rls.sql

echo "==> Done. Database is ready."
