# Stage 9 OPA Authorization Policy

Stage 9 introduces Open Policy Agent as the standalone authorization engine that
Kong will call before routing requests to microservices in later stages. The
microservices still keep their internal checks from Stage 8 for
defense-in-depth.

## Scope Implemented

- Added role-permission data in `opa/data/roles.json`.
- Added Rego helpers in `opa/policies/roles.rego`.
- Added the main authorization policy in `opa/policies/authz.rego`.
- Added Rego unit tests in `opa/tests/authz_test.rego`.
- Added `scripts/test-opa.sh` with local OPA support and Docker fallback.
- Added an `opa` service to `docker-compose.yml`.
- Attached OPA to `app-net` for Kong/internal calls and `dmz-net` only so the
  lab can smoke test the OPA HTTP API from `localhost:8181`.

## Policy Behavior

The policy defaults to deny and maps HTTP method + normalized path segment to a
permission before checking role permissions. It supports:

- `platform_admin` full access, including admin paths without tenant context.
- `tenant_admin` access based on permission mapping and non-empty tenant context.
- `tenant_user` read/write resource access only.
- Admin paths restricted to `platform_admin`.
- Missing tenant context denied for tenant-scoped roles.
- BOLA helper `deny_bola` that returns true when `resource_tenant_id` differs
  from JWT `tenant_id`.

The path normalization guard handles both `["api", "v1", "resources"]` and
`["", "api", "v1", "resources"]`, which protects the policy from Kong plugin
path-splitting differences.

## Test Commands

Run all OPA policy tests:

```powershell
bash scripts/test-opa.sh
```

Expected output:

```text
data.authz.test_default_deny_unknown_route: PASS
data.authz.test_tenant_user_get_resources_allowed: PASS
data.authz.test_tenant_user_post_resources_allowed: PASS
data.authz.test_tenant_user_delete_resources_denied: PASS
data.authz.test_tenant_user_get_admin_denied: PASS
data.authz.test_tenant_admin_delete_resources_allowed: PASS
data.authz.test_tenant_admin_get_admin_denied: PASS
data.authz.test_platform_admin_get_admin_allowed_without_tenant: PASS
data.authz.test_missing_tenant_id_tenant_user_denied: PASS
data.authz.test_path_with_leading_empty_segment_is_normalized: PASS
data.authz.test_bola_cross_tenant_denied: PASS
data.authz.test_bola_same_tenant_not_denied: PASS
PASS: 12/12
```

Validate Compose configuration and start OPA:

```powershell
docker compose config --quiet
docker compose up -d opa
docker compose ps opa
```

Expected Compose state:

```text
nt219-cloud-api-security-opa-1   openpolicyagent/opa:0.65.0   ...   Up ... (healthy)   0.0.0.0:8181->8181/tcp
```

## HTTP API Smoke Tests

Allowed tenant user resource read:

```powershell
$OPA_INPUT = New-TemporaryFile
@'
{"input":{"method":"GET","path":["api","v1","resources"],"tenant_id":"11111111-1111-1111-1111-111111111111","user_id":"u1","roles":["tenant_user"]}}
'@ | Set-Content -NoNewline $OPA_INPUT
curl.exe -s -X POST http://localhost:8181/v1/data/authz/allow -H "Content-Type: application/json" --data-binary "@$OPA_INPUT"
Remove-Item $OPA_INPUT
```

Expected output:

```json
{"result":true}
```

Denied tenant user admin read:

```powershell
$OPA_INPUT = New-TemporaryFile
@'
{"input":{"method":"GET","path":["api","v1","admin"],"tenant_id":"11111111-1111-1111-1111-111111111111","user_id":"u1","roles":["tenant_user"]}}
'@ | Set-Content -NoNewline $OPA_INPUT
curl.exe -s -X POST http://localhost:8181/v1/data/authz/allow -H "Content-Type: application/json" --data-binary "@$OPA_INPUT"
Remove-Item $OPA_INPUT
```

Expected output:

```json
{"result":false}
```

BOLA denial check:

```powershell
$OPA_INPUT = New-TemporaryFile
@'
{"input":{"tenant_id":"11111111-1111-1111-1111-111111111111","resource_tenant_id":"22222222-2222-2222-2222-222222222222","resource_id":"res-123","user_id":"u1"}}
'@ | Set-Content -NoNewline $OPA_INPUT
curl.exe -s -X POST http://localhost:8181/v1/data/authz/deny_bola -H "Content-Type: application/json" --data-binary "@$OPA_INPUT"
Remove-Item $OPA_INPUT
```

Expected output:

```json
{"result":true}
```

Same-tenant BOLA check:

```powershell
$OPA_INPUT = New-TemporaryFile
@'
{"input":{"tenant_id":"11111111-1111-1111-1111-111111111111","resource_tenant_id":"11111111-1111-1111-1111-111111111111","resource_id":"res-123","user_id":"u1"}}
'@ | Set-Content -NoNewline $OPA_INPUT
curl.exe -s -X POST http://localhost:8181/v1/data/authz/deny_bola -H "Content-Type: application/json" --data-binary "@$OPA_INPUT"
Remove-Item $OPA_INPUT
```

Expected output:

```json
{"result":false}
```
