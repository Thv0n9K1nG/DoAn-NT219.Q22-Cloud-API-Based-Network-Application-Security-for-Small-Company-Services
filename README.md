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
| PQC               | pqcrypto ML-DSA-65      | ML-DSA application-layer signatures                  |
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

Run Stage 11 TLS network-plane tests:

```bash
bash scripts/generate-dev-certs.sh
bash scripts/kong-init.sh
bash scripts/test-tls-plane.sh
```

Expected output includes:

```text
subject=CN = localhost
issuer=CN = saas-platform-internal-ca
resource-service upstream certificate verify: ok
external TLS no-token gateway request      expected=401 actual=401
Kong routes to HTTPS upstream              expected=200 actual=200
Stage 11 TLS plane test passed.
```

Generate real ML-DSA-65 keys in Vault and run the Stage 12 PQC tests:

```bash
docker compose up -d vault
bash scripts/vault-init.sh
python scripts/generate_mldsa_keys.py --vault-addr http://localhost:8200 --vault-token root-token-for-lab-only
pytest tests/test_pqc_signing.py tests/test_s2s_token.py tests/test_webhook_signer.py -v
python tests/benchmarks/benchmark_mldsa.py --iterations 20
```

Expected output includes:

```text
stored secret/pqc/s2s-signing algorithm=ML-DSA-65 public_key_bytes=1952 private_key_bytes=4032 signature_bytes=3309
stored secret/pqc/webhook-signing algorithm=ML-DSA-65 public_key_bytes=1952 private_key_bytes=4032 signature_bytes=3309
13 passed
ML-DSA-65 benchmark
signature_bytes=3309
public_key_bytes=1952
private_key_bytes=4032
```

Manual S2S token and outbound webhook usage examples:

```python
from shared.pqc_signing import MLDSASigner, S2S_SIGNING_KEY_PATH, WEBHOOK_SIGNING_KEY_PATH
from shared.s2s_token import create_s2s_token, verify_s2s_token
from shared.vault_client import VaultClient
from shared.webhook_signer import create_webhook_signature_headers, verify_webhook_signature

vault = VaultClient(addr="http://localhost:8200", token="root-token-for-lab-only")
s2s_signer = MLDSASigner.from_vault(vault, key_path=S2S_SIGNING_KEY_PATH)
webhook_signer = MLDSASigner.from_vault(vault, key_path=WEBHOOK_SIGNING_KEY_PATH)

token = create_s2s_token(
    signer=s2s_signer,
    issuer="payment-service",
    subject="payment-service",
    audience="resource-service",
    tenant_id="11111111-1111-1111-1111-111111111111",
)
claims = verify_s2s_token(
    token,
    signer=s2s_signer,
    expected_audience="resource-service",
    allowed_issuers=["payment-service"],
)

payload = {"event": "invoice.paid", "data": {"id": "inv-demo"}}
headers = create_webhook_signature_headers(payload, signer=webhook_signer)
assert verify_webhook_signature(payload, headers, signer=webhook_signer)
```

Run Stage 13 Payment Service and Stripe webhook tests:

```bash
pytest services/payment-service/tests -v
```

Expected output includes:

```text
test_create_payment_intent_uses_tenant_from_jwt PASSED
test_cross_tenant_payment_read_is_denied_and_logged PASSED
test_stripe_webhook_rejects_forged_signature PASSED
test_stripe_webhook_accepts_valid_signature_and_processes_event PASSED
```

Manual forged webhook check through Kong:

```bash
curl -k -i https://localhost:8443/webhooks/stripe \
  -H "Content-Type: application/json" \
  -H "Stripe-Signature: t=123,v1=forged" \
  -d '{"id":"evt_forged","type":"payment_intent.succeeded","data":{"object":{"id":"pi_forged"}}}'
```

Expected status:

```text
HTTP/1.1 400 Bad Request
```

Run Stage 14 observability tests and start the Loki/Grafana/Promtail stack:

```bash
pytest tests/test_observability_config.py services/resource-service/tests/test_logging.py services/payment-service/tests/test_stripe_webhook.py -v
docker compose config --quiet
docker compose up -d --force-recreate loki grafana promtail
```

Expected output includes:

```text
9 passed
Container nt219-cloud-api-security-loki-1     Healthy
Container nt219-cloud-api-security-grafana-1  Healthy
Container nt219-cloud-api-security-promtail-1 Started
```

Verify Loki and Grafana provisioning:

```bash
curl.exe -s http://127.0.0.1:3100/ready
curl.exe -s -u admin:changeme-grafana http://127.0.0.1:3000/api/health
curl.exe -s -u admin:changeme-grafana http://127.0.0.1:3000/api/datasources/uid/loki
curl.exe -s -u admin:changeme-grafana "http://127.0.0.1:3000/api/search?query=NT219"
curl.exe -s -u admin:changeme-grafana http://127.0.0.1:3000/api/v1/provisioning/alert-rules
```

Expected output includes `ready`, Grafana database status `ok`, datasource UID
`loki`, dashboards `NT219 API Traffic Overview`, `NT219 Security Events`,
`NT219 Tenant Activity`, and alert rules `HighAuthFailureRate`,
`BOLAAttemptDetected`, `RateLimitViolation`, `StripeWebhookFailure`.

Run Stage 15 local CI/security checks before pushing:

```bash
python -m pip install -r requirements-dev.txt
bash scripts/test-ci-security.sh
docker run --rm -v "${PWD}:/src" -w /src semgrep/semgrep:1.100.0 semgrep scan --config=p/python --config=p/jwt --config=p/secrets --metrics=off --error --json --output=tests/reports/semgrep-report.json services shared scripts opa
docker compose build user-service resource-service admin-service payment-service
```

Expected output includes `58 passed`, `PASS: 14/14`,
`No known vulnerabilities found`, `0 findings`, and all four service images
built successfully.

Run Stage 16 security attack simulations:

```bash
python -m pytest tests/attacks -v --tb=short
bash tests/run_security_tests.sh
```

Expected output includes:

```text
18 passed
PASS: 14/14
58 passed
FAIL-NEW: 0
WARN-NEW: 2
```

See `docs/stage-16-security-testing.md` for the attack matrix, observed ZAP
warnings, current limits, and next hardening tasks.

Expected full-stack workflow for later stages:

```bash
docker compose up -d
```

Use `docker-compose.dev.yml` for service hot reload overrides in later stages.

## Current Stage

Completed: Stage 16 - Security testing and attack simulation.

Next: Stage 17 - Evaluation metrics, runbooks, final docs, and demo package.

## Safety Notes

- Do not commit `.env`, private keys, certificates, generated reports, or logs.
- The `.context/` directory is local working context and is intentionally ignored.
- Attack simulations must run only against this lab environment.
- ML-DSA is used at the application layer. This project does not claim
  post-quantum TLS.
