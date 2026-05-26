\set ON_ERROR_STOP on

SELECT 'RLS status' AS check_name, relname, relrowsecurity, relforcerowsecurity
FROM pg_class
WHERE relname = 'resources';

BEGIN;
SET LOCAL ROLE resource_service_app;
SET LOCAL app.current_tenant = '11111111-1111-1111-1111-111111111111';
SELECT 'alpha visible resources' AS check_name, id, name, tenant_id
FROM resources
ORDER BY name;
DO $$
DECLARE
  visible_count INTEGER;
  wrong_count INTEGER;
BEGIN
  SELECT count(*) INTO visible_count FROM resources;
  SELECT count(*) INTO wrong_count
  FROM resources
  WHERE tenant_id <> '11111111-1111-1111-1111-111111111111'::uuid;

  IF visible_count <> 1 OR wrong_count <> 0 THEN
    RAISE EXCEPTION 'alpha RLS isolation failed: visible %, wrong %', visible_count, wrong_count;
  END IF;
END;
$$;
COMMIT;

BEGIN;
SET LOCAL ROLE resource_service_app;
SET LOCAL app.current_tenant = '22222222-2222-2222-2222-222222222222';
SELECT 'beta visible resources' AS check_name, id, name, tenant_id
FROM resources
ORDER BY name;
DO $$
DECLARE
  visible_count INTEGER;
  wrong_count INTEGER;
BEGIN
  SELECT count(*) INTO visible_count FROM resources;
  SELECT count(*) INTO wrong_count
  FROM resources
  WHERE tenant_id <> '22222222-2222-2222-2222-222222222222'::uuid;

  IF visible_count <> 1 OR wrong_count <> 0 THEN
    RAISE EXCEPTION 'beta RLS isolation failed: visible %, wrong %', visible_count, wrong_count;
  END IF;
END;
$$;
COMMIT;

BEGIN;
SET LOCAL ROLE resource_service_app;
SELECT 'no tenant context visible count' AS check_name, count(*) AS visible_count
FROM resources;
DO $$
DECLARE
  visible_count INTEGER;
BEGIN
  SELECT count(*) INTO visible_count FROM resources;

  IF visible_count <> 0 THEN
    RAISE EXCEPTION 'missing tenant context should see 0 resources, saw %', visible_count;
  END IF;
END;
$$;
COMMIT;
