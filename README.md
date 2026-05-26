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

| Layer | Technology | Role |
| --- | --- | --- |
| API Gateway | Kong OSS | TLS termination, JWT validation, rate limit, routing |
| Identity Provider | Keycloak | OAuth2/OIDC, organizations, JWT issuance |
| Authorization | OPA | RBAC/ABAC policy decision point |
| Secrets | HashiCorp Vault | Secrets, transit keys, PKI material |
| Services | Python FastAPI | User, resource, admin, and payment APIs |
| Database | PostgreSQL | Tenant data and row-level security |
| Cache/State | Redis | Gateway rate limiting state |
| Observability | Grafana, Loki, Promtail | Logs, dashboards, alerts |
| PQC | liboqs / oqs-python | ML-DSA application-layer signatures |
| CI/CD | GitHub Actions | SAST, dependency scan, tests, builds |
| Deployment | Docker Compose | Local lab runtime |

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
docker compose --profile observability up -d promtail
```

Expected full-stack workflow for later stages:

```bash
docker compose up -d
```

Use `docker-compose.dev.yml` for service hot reload overrides in later stages.

## Current Stage

Completed: Stage 3 - SQL-script database schema, deterministic seed data, and
PostgreSQL row-level security proof for tenant-owned resources.

Next: Stage 4 - Keycloak realm, clients, roles, users, and JWT tenant claims.

## Safety Notes

- Do not commit `.env`, private keys, certificates, generated reports, or logs.
- The `.context/` directory is local working context and is intentionally ignored.
- Attack simulations must run only against this lab environment.
- ML-DSA is used at the application layer. This project does not claim
  post-quantum TLS.
