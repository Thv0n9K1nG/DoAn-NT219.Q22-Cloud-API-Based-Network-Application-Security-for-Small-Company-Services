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
