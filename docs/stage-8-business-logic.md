# Stage 8 Business Logic and Tenant Isolation

Stage 8 turns the Stage 7 FastAPI skeletons into usable tenant-aware APIs for
User, Resource, and Admin services. The implementation keeps route-level
authorization explicit and puts database access in service classes so later
stages can add OPA/Kong without removing defense-in-depth checks from the
microservices.

## Scope Implemented

- User Service now supports tenant-scoped list, self/profile read,
  tenant-admin create/update, and soft deactivation.
- Resource Service now supports tenant-scoped list/create/read/update/delete.
  The service never accepts `tenant_id` from request bodies for resource
  creation; it derives ownership from the verified JWT context.
- Admin Service now supports platform-admin tenant listing, tenant onboarding,
  tenant stats, and a tenant key rotation placeholder response.
- Shared API errors include `BAD_REQUEST`, `NOT_FOUND`, and `CONFLICT` codes for
  business endpoints.
- Tests cover role checks, tenant boundary checks, BOLA denial, and JSON BOLA
  security logging.

## Authorization Notes

JWT claims remain the source of truth after signature validation. Client-supplied
tenant IDs are not trusted for tenant-owned operations. Tenant admins are limited
to their own tenant, while platform admins can use cross-tenant admin flows where
the stage requires it.

For local lab seed data, User Service also supports a self-profile fallback from
Keycloak `sub` to `email + tenant_id`. This keeps real Keycloak tokens usable
even when deterministic SQL seed rows use lab aliases such as `kc-alpha-user`.
The fallback is only allowed for the current user and still requires tenant
match.

Resource reads intentionally fetch the resource first and then compare the
record's `tenant_id` to the JWT tenant. This lets the service log a useful
`security.bola_attempt` event with `user_id`, attacker tenant, resource ID, and
actual resource tenant before returning `403`.

## Database Preparation

Stage 8 services use separate Compose databases:

- `user-service` -> `userdb`
- `resource-service` -> `resourcedb`
- `admin-service` -> `admindb`

Apply the SQL scripts to the service databases before doing manual API demos.
RLS is applied only to `resourcedb` because Resource Service owns tenant-scoped
resource access.

```powershell
cmd /c "type scripts\db-init.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d userdb"
cmd /c "type scripts\seed-data.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d userdb"

cmd /c "type scripts\db-init.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d resourcedb"
cmd /c "type scripts\apply-rls.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d resourcedb"
cmd /c "type scripts\seed-data.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d resourcedb"

cmd /c "type scripts\db-init.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d admindb"
cmd /c "type scripts\seed-data.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d admindb"
```

## Test Commands

```powershell
python -m pip install -r requirements-dev.txt
pytest services/user-service/tests services/resource-service/tests services/admin-service/tests -v
pytest -v
docker compose build user-service resource-service admin-service payment-service
docker compose up -d postgres vault keycloak user-service resource-service admin-service payment-service
```

For a manual BOLA demo, generate Keycloak lab tokens, create an alpha resource,
then try to read it using a beta token through the Resource Service container or
later through Kong once gateway routing is available.

## Manual BOLA Demo With Curl

Stage 8 does not expose microservice ports on the host. Until Kong is wired in a
later stage, run `curl` from a temporary container on the Compose `app-net`
network so it can reach `http://resource-service:8000`.

First make sure the lab services and Keycloak users are ready:

```powershell
docker compose up -d postgres vault keycloak user-service resource-service admin-service payment-service
bash scripts/keycloak-init.sh
```

Create an alpha resource, then try to read it as a beta user. The beta read
should return `403 ACCESS_DENIED`.

```powershell
$ALPHA_TOKEN = bash scripts/get-token.sh alpha-user@example.com 'TestPass123!'
$BETA_TOKEN = bash scripts/get-token.sh beta-user@example.com 'TestPass123!'

$UNIQUE_NAME = "stage8-bola-demo-$([guid]::NewGuid().ToString('N'))"

$BODY = @{
  name = $UNIQUE_NAME
  data = @{
    classification = "confidential"
    demo = "bola"
  }
} | ConvertTo-Json -Compress

Write-Host "Request body:"
Write-Host $BODY

$CREATE_RESPONSE = $BODY | docker run --rm -i `
  --network nt219-cloud-api-security_app-net `
  curlimages/curl:8.10.1 -sS `
  -X POST "http://resource-service:8000/api/v1/resources" `
  -H "Authorization: Bearer $ALPHA_TOKEN" `
  -H "Content-Type: application/json" `
  --data-binary '@-'

Write-Host "`nCreate response:"
Write-Host $CREATE_RESPONSE

$CREATE_JSON = $CREATE_RESPONSE | ConvertFrom-Json
$RESOURCE_ID = $CREATE_JSON.id

if ([string]::IsNullOrWhiteSpace($RESOURCE_ID)) {
  Write-Host "`nERROR: Resource was not created. Stop here."
  exit 1
}

Write-Host "`nResource ID:"
Write-Host $RESOURCE_ID

Write-Host "`nBeta user tries to read Alpha resource:"
docker run --rm `
  --network nt219-cloud-api-security_app-net `
  curlimages/curl:8.10.1 -i `
  "http://resource-service:8000/api/v1/resources/$RESOURCE_ID" `
  -H "Authorization: Bearer $BETA_TOKEN"
```

Expected beta response:

```text
HTTP/1.1 403 Forbidden
...
{"error":{"code":"ACCESS_DENIED","message":"Access denied",...}}
```

Confirm the BOLA event is logged with attacker and resource tenant metadata:

```powershell
docker compose logs --tail=80 resource-service | Select-String "security.bola_attempt|$RESOURCE_ID"
```
