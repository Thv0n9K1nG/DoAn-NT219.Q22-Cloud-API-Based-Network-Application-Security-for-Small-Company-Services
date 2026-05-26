\set ON_ERROR_STOP on

BEGIN;

INSERT INTO tenants (id, name, status)
VALUES
  ('11111111-1111-1111-1111-111111111111', 'tenant-alpha', 'active'),
  ('22222222-2222-2222-2222-222222222222', 'tenant-beta', 'active')
ON CONFLICT (id) DO UPDATE
SET name = EXCLUDED.name,
    status = EXCLUDED.status;

INSERT INTO users (id, keycloak_user_id, tenant_id, email, role, status)
VALUES
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1', 'kc-alpha-admin', '11111111-1111-1111-1111-111111111111', 'alpha-admin@example.com', 'tenant_admin', 'active'),
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2', 'kc-alpha-user', '11111111-1111-1111-1111-111111111111', 'alpha-user@example.com', 'tenant_user', 'active'),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb1', 'kc-beta-admin', '22222222-2222-2222-2222-222222222222', 'beta-admin@example.com', 'tenant_admin', 'active'),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb2', 'kc-beta-user', '22222222-2222-2222-2222-222222222222', 'beta-user@example.com', 'tenant_user', 'active'),
  ('cccccccc-cccc-cccc-cccc-ccccccccccc1', 'kc-platform-admin', '11111111-1111-1111-1111-111111111111', 'platform-admin@example.com', 'platform_admin', 'active')
ON CONFLICT (id) DO UPDATE
SET keycloak_user_id = EXCLUDED.keycloak_user_id,
    tenant_id = EXCLUDED.tenant_id,
    email = EXCLUDED.email,
    role = EXCLUDED.role,
    status = EXCLUDED.status;

INSERT INTO resources (id, tenant_id, owner_user_id, name, data, url)
VALUES
  (
    'aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa',
    '11111111-1111-1111-1111-111111111111',
    'kc-alpha-user',
    'alpha-secret',
    '{"classification": "confidential", "example": "alpha-only"}'::jsonb,
    'https://alpha.example.test/resource'
  ),
  (
    'bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb',
    '22222222-2222-2222-2222-222222222222',
    'kc-beta-user',
    'beta-secret',
    '{"classification": "confidential", "example": "beta-only"}'::jsonb,
    'https://beta.example.test/resource'
  )
ON CONFLICT (id) DO UPDATE
SET tenant_id = EXCLUDED.tenant_id,
    owner_user_id = EXCLUDED.owner_user_id,
    name = EXCLUDED.name,
    data = EXCLUDED.data,
    url = EXCLUDED.url;

INSERT INTO payments (id, tenant_id, user_id, stripe_payment_intent_id, amount, currency, status)
VALUES
  ('dddddddd-1111-1111-1111-dddddddddddd', '11111111-1111-1111-1111-111111111111', 'kc-alpha-user', 'pi_alpha_stage3_seed', 1999, 'usd', 'succeeded'),
  ('eeeeeeee-2222-2222-2222-eeeeeeeeeeee', '22222222-2222-2222-2222-222222222222', 'kc-beta-user', 'pi_beta_stage3_seed', 2999, 'usd', 'succeeded')
ON CONFLICT (id) DO UPDATE
SET tenant_id = EXCLUDED.tenant_id,
    user_id = EXCLUDED.user_id,
    stripe_payment_intent_id = EXCLUDED.stripe_payment_intent_id,
    amount = EXCLUDED.amount,
    currency = EXCLUDED.currency,
    status = EXCLUDED.status;

COMMIT;
