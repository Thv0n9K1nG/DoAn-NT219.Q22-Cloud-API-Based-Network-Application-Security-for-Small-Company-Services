# Database Schema

Stage 3 uses SQL scripts as the migration strategy. Alembic is intentionally not
introduced yet so the lab can prove tenant isolation with plain PostgreSQL.

## Scripts

| Script                  | Purpose                                                                  |
| ----------------------- | ------------------------------------------------------------------------ |
| `scripts/db-init.sql`   | Creates tables, indexes, triggers, and service roles                     |
| `scripts/apply-rls.sql` | Enables and forces RLS on `resources`                                    |
| `scripts/seed-data.sql` | Inserts deterministic alpha/beta tenants, users, resources, and payments |
| `scripts/test-rls.sql`  | Proves tenant isolation as `resource_service_app`                        |

## Payment Webhook Idempotency

Stage 13 adds `stripe_webhook_events` to record processed Stripe event IDs. This
table prevents duplicate side effects when Stripe retries the same event.

| Column              | Purpose                                      |
| ------------------- | -------------------------------------------- |
| `event_id`          | Stripe event ID, primary key                 |
| `event_type`        | Stripe event type, for example `payment_intent.succeeded` |
| `payment_intent_id` | Related Stripe Payment Intent ID             |
| `processed_at`      | Server-side processing timestamp             |

## Tenant IDs

| Tenant         | UUID                                   |
| -------------- | -------------------------------------- |
| `tenant-alpha` | `11111111-1111-1111-1111-111111111111` |
| `tenant-beta`  | `22222222-2222-2222-2222-222222222222` |

## RLS Contract

The service layer must set tenant context inside the transaction before reading
or writing tenant-owned resources:

```sql
SET LOCAL app.current_tenant = '<tenant_id_from_verified_jwt>';
```

The `resources` table policy compares `tenant_id` with
`current_setting('app.current_tenant', true)`. If the setting is absent, the
application role sees zero resources.

## PowerShell Test Commands

```powershell
docker compose up -d postgres
cmd /c "type scripts\db-init.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d resourcedb"
cmd /c "type scripts\apply-rls.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d resourcedb"
cmd /c "type scripts\seed-data.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d resourcedb"
cmd /c "type scripts\test-rls.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d resourcedb"
```

Expected result:

- RLS status is `relrowsecurity = t` and `relforcerowsecurity = t`.
- Alpha tenant sees only `alpha-secret`.
- Beta tenant sees only `beta-secret`.
- No tenant context sees `0` resources.
