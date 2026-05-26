\set ON_ERROR_STOP on

BEGIN;

CREATE SCHEMA IF NOT EXISTS app;

-- Resolve the tenant context set by the API layer before each query.
CREATE OR REPLACE FUNCTION app.current_tenant_id()
RETURNS UUID
LANGUAGE sql
STABLE
AS $$
  SELECT nullif(current_setting('app.current_tenant', true), '')::uuid;
$$;

ALTER TABLE resources ENABLE ROW LEVEL SECURITY;
ALTER TABLE resources FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_select ON resources;
CREATE POLICY tenant_isolation_select ON resources
  FOR SELECT
  USING (tenant_id = app.current_tenant_id());

DROP POLICY IF EXISTS tenant_isolation_insert ON resources;
CREATE POLICY tenant_isolation_insert ON resources
  FOR INSERT
  WITH CHECK (tenant_id = app.current_tenant_id());

DROP POLICY IF EXISTS tenant_isolation_update ON resources;
CREATE POLICY tenant_isolation_update ON resources
  FOR UPDATE
  USING (tenant_id = app.current_tenant_id())
  WITH CHECK (tenant_id = app.current_tenant_id());

DROP POLICY IF EXISTS tenant_isolation_delete ON resources;
CREATE POLICY tenant_isolation_delete ON resources
  FOR DELETE
  USING (tenant_id = app.current_tenant_id());

COMMIT;
