# Architecture Notes

This Stage 1 placeholder records the target architecture at a high level. It
will be expanded as the runtime stack is implemented.

## Target Topology

```text
Client
  -> Kong on dmz-net
  -> Keycloak, OPA, Vault, FastAPI services on app-net
  -> PostgreSQL, Redis, Loki on data-net
  -> Grafana exposed for lab observability
```

## Docker Networks

| Network | Exposure | Current Stage 2 Members |
| --- | --- | --- |
| `dmz-net` | Host-facing bridge | `grafana`, `keycloak` |
| `app-net` | Internal bridge | `redis`, `vault`, `keycloak` |
| `data-net` | Internal bridge | `postgres`, `redis`, `keycloak`, `loki`, `grafana`, optional `promtail` |

Grafana is exposed through `localhost:3000`. Starting in Stage 4, Keycloak is
also exposed through `localhost:18080` for lab token and JWKS checks only.
PostgreSQL, Redis, Vault, and Loki stay on internal Docker networks.

## Base Infrastructure

| Service | Image | Purpose | Host Port |
| --- | --- | --- | --- |
| `postgres` | `postgres:16-alpine` | Shared PostgreSQL server with stage databases | None |
| `redis` | `redis:7-alpine` | Rate limit state for Kong in later stages | None |
| `vault` | `hashicorp/vault:1.16` | Lab-only Vault dev server | None |
| `keycloak` | `quay.io/keycloak/keycloak:24.0` | OIDC provider foundation | `18080` |
| `loki` | `grafana/loki:3.0.0` | Log backend | None |
| `grafana` | `grafana/grafana:10.4.0` | Dashboards and Loki UI | `3000` |
| `promtail` | `grafana/promtail:3.0.0` | Optional log shipper profile | None |

## Microservices

| Service | Port | Responsibility |
| --- | --- | --- |
| user-service | 8001 | User profiles and tenant membership data |
| resource-service | 8002 | Tenant-owned resources and BOLA checks |
| admin-service | 8003 | Platform and tenant administration |
| payment-service | 8004 | Stripe sandbox payments and webhooks |

## Security Enforcement Points

| Point | Responsibility |
| --- | --- |
| Keycloak | User authentication and JWT issuance |
| Kong | API perimeter, JWT validation, rate limiting, routing |
| OPA | RBAC/ABAC authorization decisions |
| Services | Business authorization and tenant ownership checks |
| PostgreSQL | Data isolation with row-level security |
| Vault | Secret and key management |
| Loki/Grafana | Detection, dashboards, and alerting |

## Stage 3 Data Model

SQL scripts in `scripts/` are the migration source for this stage. The prototype
schema contains:

| Table | Purpose | Tenant-owned |
| --- | --- | --- |
| `tenants` | Tenant registry for alpha and beta lab tenants | No |
| `users` | Application profile mapped to Keycloak users | Yes |
| `resources` | Tenant-owned resource records used for BOLA/RLS tests | Yes |
| `payments` | Stripe sandbox payment records | Yes |

`resources` has PostgreSQL RLS enabled and forced. API code must set
`app.current_tenant` from a verified JWT before querying tenant-owned resources.
