# Source Mapping

This file maps the design document sections to implementation locations so each
stage can be checked against the project scope.

| Source | Implementation Target |
| --- | --- |
| `project-spec.md` section 1 | `README.md`, `docs/architecture.md` |
| `project-spec.md` section 2 | `README.md`, `docker-compose.yml`, `services/*/requirements.txt` |
| `project-spec.md` section 3 | `docker-compose.yml`, network definitions |
| `project-spec.md` section 4 | DB schema, Keycloak realm, Vault transit keys |
| `project-spec.md` section 5 | `idp/realm-export.json` |
| `project-spec.md` section 6 | `gateway/kong.yml`, `scripts/kong-init.sh` |
| `project-spec.md` section 7 | `opa/policies/authz.rego`, `opa/data/roles.json` |
| `project-spec.md` section 8 | `scripts/vault-init.sh`, `shared/vault_client.py` |
| `project-spec.md` section 9 | `shared/pqc_signing.py`, `shared/s2s_token.py`, `shared/webhook_signer.py` |
| `project-spec.md` section 10 | `services/user-service`, `services/resource-service`, `services/admin-service`, `services/payment-service` |
| `project-spec.md` section 11 | `services/payment-service` |
| `project-spec.md` section 12 | `observability/` |
| `project-spec.md` section 13 | `.github/workflows/` |
| `project-spec.md` section 14 | `docker-compose.yml`, `.env.example` |
| `project-spec.md` section 15 | `tests/attacks/`, `tests/run_security_tests.sh` |
| `project-spec.md` section 16 | `docs/threat-model.md` |
| `project-spec.md` section 17 | `runbooks/` |
| `project-spec.md` section 18 | Repository structure |
| `project-spec.md` section 19 | `docs/evaluation.md`, `tests/benchmarks/` |
| `project-spec.md` section 20 | `docs/limitations.md` |

## Stage Mapping

| Stage | Main Deliverable |
| --- | --- |
| 01 | Repository skeleton, README, threat model, source mapping |
| 02 | Docker Compose base, networks, infra health checks |
| 03 | Database schema, seed data, row-level security |
| 04 | Keycloak realm and JWT claims |
| 05 | Shared JWT, headers, and logging library |
| 06 | Vault KV, Transit, AppRole, PKI setup |
| 07 | FastAPI service skeletons |
| 08 | CRUD, tenant isolation, BOLA checks |
| 09 | OPA policies and tests |
| 10 | Kong routes, JWT validation, rate limiting, WAF-lite |
| 11 | TLS and upstream mTLS |
| 12 | ML-DSA signing and verification |
| 13 | Stripe payment and webhook security |
| 14 | Loki, Grafana dashboards, alerts |
| 15 | CI/CD security automation |
| 16 | Attack simulations and ZAP |
| 17 | Evaluation, runbooks, final docs, demo package |
