-- ============================================================
-- Migration 001: Enable Row-Level Security on all tenant tables
-- ============================================================
-- Apply this ONCE against your PostgreSQL database:
--   psql $DATABASE_URL -f backend/migrations/001_enable_rls.sql
--
-- RLS policy: every query must set app.current_tenant_id:
--   SET LOCAL app.current_tenant_id = '<tenant_id>';
-- ============================================================

-- Enable RLS on all tables
ALTER TABLE "Tenant" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "User" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "Integration" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "Tool" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "Execution" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "Approval" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "AuditLog" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "Invoice" ENABLE ROW LEVEL SECURITY;

-- Force RLS even for table owners (important for superuser connections)
ALTER TABLE "User" FORCE ROW LEVEL SECURITY;
ALTER TABLE "Integration" FORCE ROW LEVEL SECURITY;
ALTER TABLE "Tool" FORCE ROW LEVEL SECURITY;
ALTER TABLE "Execution" FORCE ROW LEVEL SECURITY;
ALTER TABLE "Approval" FORCE ROW LEVEL SECURITY;
ALTER TABLE "AuditLog" FORCE ROW LEVEL SECURITY;
ALTER TABLE "Invoice" FORCE ROW LEVEL SECURITY;

-- Tenant table: users can only see their own tenant
CREATE POLICY tenant_select ON "Tenant"
    FOR SELECT
    USING (id = current_setting('app.current_tenant_id', true));

-- User table
CREATE POLICY user_select ON "User"
    FOR SELECT
    USING (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY user_insert ON "User"
    FOR INSERT
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY user_update ON "User"
    FOR UPDATE
    USING (tenant_id = current_setting('app.current_tenant_id', true));

-- Integration table
CREATE POLICY integration_select ON "Integration"
    FOR SELECT
    USING (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY integration_insert ON "Integration"
    FOR INSERT
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY integration_update ON "Integration"
    FOR UPDATE
    USING (tenant_id = current_setting('app.current_tenant_id', true));

-- Tool table
CREATE POLICY tool_select ON "Tool"
    FOR SELECT
    USING (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tool_insert ON "Tool"
    FOR INSERT
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY tool_update ON "Tool"
    FOR UPDATE
    USING (tenant_id = current_setting('app.current_tenant_id', true));

-- Execution table
CREATE POLICY execution_select ON "Execution"
    FOR SELECT
    USING (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY execution_insert ON "Execution"
    FOR INSERT
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));

-- Approval table
CREATE POLICY approval_select ON "Approval"
    FOR SELECT
    USING (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY approval_insert ON "Approval"
    FOR INSERT
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY approval_update ON "Approval"
    FOR UPDATE
    USING (tenant_id = current_setting('app.current_tenant_id', true));

-- AuditLog table (APPEND ONLY — no UPDATE or DELETE policies, ever)
CREATE POLICY auditlog_select ON "AuditLog"
    FOR SELECT
    USING (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY auditlog_insert ON "AuditLog"
    FOR INSERT
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));

-- Invoice table
CREATE POLICY invoice_select ON "Invoice"
    FOR SELECT
    USING (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY invoice_insert ON "Invoice"
    FOR INSERT
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY invoice_update ON "Invoice"
    FOR UPDATE
    USING (tenant_id = current_setting('app.current_tenant_id', true));

-- BankAccount table
ALTER TABLE "BankAccount" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "BankAccount" FORCE ROW LEVEL SECURITY;

CREATE POLICY bankaccount_select ON "BankAccount"
    FOR SELECT
    USING (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY bankaccount_insert ON "BankAccount"
    FOR INSERT
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY bankaccount_update ON "BankAccount"
    FOR UPDATE
    USING (tenant_id = current_setting('app.current_tenant_id', true));

-- BankTransaction table
ALTER TABLE "BankTransaction" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "BankTransaction" FORCE ROW LEVEL SECURITY;

CREATE POLICY banktransaction_select ON "BankTransaction"
    FOR SELECT
    USING (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY banktransaction_insert ON "BankTransaction"
    FOR INSERT
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));

CREATE POLICY banktransaction_update ON "BankTransaction"
    FOR UPDATE
    USING (tenant_id = current_setting('app.current_tenant_id', true));
