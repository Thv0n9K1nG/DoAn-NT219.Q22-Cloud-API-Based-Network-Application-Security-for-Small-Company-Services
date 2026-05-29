# Cloud API-Based Network Application Security for Small Company Services

NT219 cryptography capstone project for a small multi-tenant SaaS platform.

## Instructor

- Nguyễn Ngọc Tự, PhD.

## Implemented by Group 11 consisting of:

- Hồ Ngọc Vương Thương - 24521749

- Phạm Trần Anh Tuấn - 24521939

- Nguyễn Thành Phước - 24521410

## Class

NT219.Q22.ANTT

## Goal

This project models a low-cost security architecture for small company services.
It protects API traffic, tenant data, service-to-service calls, secrets, and
security telemetry in a Docker Compose lab environment.

Core security goals:

- Authenticate users and integrators with OAuth2/OIDC through Keycloak.
- Enforce API gateway controls with Kong: JWT validation, rate limiting, WAF-lite
  rules, request IDs, and route isolation.
- Authorize requests with OPA policies and service-level tenant checks.
- Isolate tenant-owned data with explicit `tenant_id` handling and PostgreSQL
  row-level security in later stages.
- Store sensitive configuration and signing material through HashiCorp Vault.
- Demonstrate post-quantum application-layer signing with ML-DSA for S2S tokens
  and outbound webhooks. TLS remains classical in this prototype.
- Collect structured logs and alerts with Loki and Grafana.

## Scenario

The target scenario is a small multi-tenant SaaS platform. Each tenant has its
own users, roles, resources, payment records, policies, and audit trail.

Main actors:

- Tenant Admin: manages users and tenant settings.
- Tenant User: accesses tenant resources through the API.
- System Admin: operates the platform and admin APIs.
- Third-party Integrator: calls APIs with client credentials.
- Stripe: sends payment webhooks to the payment service.

## Technology Stack

| Layer             | Technology              | Role                                                 |
| ----------------- | ----------------------- | ---------------------------------------------------- |
| API Gateway       | Kong OSS                | TLS termination, JWT validation, rate limit, routing |
| Identity Provider | Keycloak                | OAuth2/OIDC, organizations, JWT issuance             |
| Authorization     | OPA                     | RBAC/ABAC policy decision point                      |
| Secrets           | HashiCorp Vault         | Secrets, transit keys, PKI material                  |
| Services          | Python FastAPI          | User, resource, admin, and payment APIs              |
| Database          | PostgreSQL              | Tenant data and row-level security                   |
| Cache/State       | Redis                   | Gateway rate limiting state                          |
| Observability     | Grafana, Loki, Promtail | Logs, dashboards, alerts                             |
| PQC               | liboqs / oqs-python     | ML-DSA application-layer signatures                  |
| CI/CD             | GitHub Actions          | SAST, dependency scan, tests, builds                 |
| Deployment        | Docker Compose          | Local lab runtime                                    |

## Request Flow

```text
Client / SPA
  -> Keycloak Authorization Code + PKCE
  -> Kong API Gateway
     -> validates Keycloak JWT
     -> applies per-tenant and per-user rate limits
     -> injects request, tenant, and user headers
     -> asks OPA for authorization
  -> FastAPI microservice
     -> enforces tenant isolation and business rules
     -> reads/writes PostgreSQL
     -> emits structured logs to Loki
  -> Response
```

## Repository Layout

```text
.github/workflows/        CI pipelines
services/                 FastAPI microservices
shared/                   Shared Python security/logging libraries
gateway/                  Kong config, plugins, TLS cert placeholders
idp/                      Keycloak realm export
opa/                      Rego policies, test data, OPA tests
vault/                    Vault configuration
observability/            Grafana, Loki, and Promtail configuration
scripts/                  Setup and operational scripts
tests/                    Attack simulations and reports
runbooks/                 Incident and operations runbooks
docs/                     Architecture, threat model, mappings, reports
demo/                     Demo script and synthetic data
```

## Local Development

Stage 2 provides the base infrastructure containers. Application services,
gateway routes, policies, and schemas are still implemented in later stages.

Create a local environment file:

```bash
cp .env.example .env
```

Start the base infrastructure:

```bash
docker compose up -d postgres redis vault loki grafana
```

Apply the Stage 3 database schema and RLS demo data:

```bash
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d resourcedb < scripts/db-init.sql
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d resourcedb < scripts/apply-rls.sql
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d resourcedb < scripts/seed-data.sql
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d resourcedb < scripts/test-rls.sql
```

Optional services:

```bash
docker compose up -d keycloak
bash scripts/keycloak-init.sh
docker compose --profile observability up -d promtail
```

Get a lab access token from Keycloak:

```bash
bash scripts/get-token.sh alpha-user@example.com 'TestPass123!'
python scripts/test-keycloak-claims.py
```

Run the Stage 5 shared security tests:

```bash
python -m pip install -r requirements-dev.txt
pytest services/resource-service/tests -v
```

Initialize Vault and run the Stage 6 wrapper tests:

```bash
docker compose up -d vault
bash scripts/vault-init.sh
pytest tests/test_vault_client.py -v
```

Build and test the Stage 7 microservice skeletons and Stage 8 business APIs:

```bash
pytest services/user-service/tests services/resource-service/tests services/admin-service/tests services/payment-service/tests -v
docker compose build user-service resource-service admin-service payment-service
docker compose up -d postgres vault keycloak user-service resource-service admin-service payment-service
```

Apply the service schemas used by Stage 8 CRUD endpoints:

```powershell
cmd /c "type scripts\db-init.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d userdb"
cmd /c "type scripts\seed-data.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d userdb"
cmd /c "type scripts\db-init.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d resourcedb"
cmd /c "type scripts\apply-rls.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d resourcedb"
cmd /c "type scripts\seed-data.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d resourcedb"
cmd /c "type scripts\db-init.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d admindb"
cmd /c "type scripts\seed-data.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d admindb"
```

Run a Stage 8 BOLA demo with `curl`. Microservice ports are internal before the
Kong stage, so this uses a temporary curl container on Compose `app-net`:

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

docker compose logs --tail=80 resource-service | Select-String "security.bola_attempt|$RESOURCE_ID"
```

Expected result: beta receives `403 ACCESS_DENIED`, and Resource Service logs a
`security.bola_attempt` event with attacker tenant and resource tenant IDs.

Run Stage 9 OPA policy tests and start the OPA server:

```bash
bash scripts/test-opa.sh
docker compose up -d opa
```

Smoke test OPA allow/deny decisions:

```powershell
$OPA_INPUT = New-TemporaryFile
@'
{"input":{"method":"GET","path":["api","v1","resources"],"tenant_id":"11111111-1111-1111-1111-111111111111","user_id":"u1","roles":["tenant_user"]}}
'@ | Set-Content -NoNewline $OPA_INPUT
curl.exe -s -X POST http://localhost:8181/v1/data/authz/allow -H "Content-Type: application/json" --data-binary "@$OPA_INPUT"

@'
{"input":{"method":"GET","path":["api","v1","admin"],"tenant_id":"11111111-1111-1111-1111-111111111111","user_id":"u1","roles":["tenant_user"]}}
'@ | Set-Content -NoNewline $OPA_INPUT
curl.exe -s -X POST http://localhost:8181/v1/data/authz/allow -H "Content-Type: application/json" --data-binary "@$OPA_INPUT"

@'
{"input":{"tenant_id":"11111111-1111-1111-1111-111111111111","resource_tenant_id":"22222222-2222-2222-2222-222222222222","resource_id":"res-123","user_id":"u1"}}
'@ | Set-Content -NoNewline $OPA_INPUT
curl.exe -s -X POST http://localhost:8181/v1/data/authz/deny_bola -H "Content-Type: application/json" --data-binary "@$OPA_INPUT"
Remove-Item $OPA_INPUT
```

Expected outputs are `{"result":true}`, `{"result":false}`, and
`{"result":true}` respectively.

Run Stage 10 Kong gateway smoke tests:

```bash
bash scripts/kong-init.sh
docker compose up -d postgres redis vault keycloak opa user-service resource-service admin-service payment-service kong
bash scripts/test-kong-gateway.sh
```

Expected output includes:

```text
no token is rejected by gateway            expected=401 actual=401
tenant user can list resources             expected=200 actual=200
tenant user is denied admin route by OPA   expected=403 actual=403
non-json API write is rejected             expected=415 actual=415
stripe webhook route bypasses JWT          expected=not-401 actual=404
rate limit status summary:
     20 200
      5 429
Stage 10 Kong gateway smoke test passed.
```

Expected full-stack workflow for later stages:

```bash
docker compose up -d
```

Use `docker-compose.dev.yml` for service hot reload overrides in later stages.

## Current Stage

Completed: Stage 10 - Kong DB-less gateway routes, JWT validation,
OPA authorization plugin, tenant header injection, Redis-backed rate limiting,
WAF-lite controls, and gateway smoke tests.

Next: Stage 11 - TLS external and mTLS between Kong and microservices.

## Safety Notes

- Do not commit `.env`, private keys, certificates, generated reports, or logs.
- The `.context/` directory is local working context and is intentionally ignored.
- Attack simulations must run only against this lab environment.
- ML-DSA is used at the application layer. This project does not claim
  post-quantum TLS.
