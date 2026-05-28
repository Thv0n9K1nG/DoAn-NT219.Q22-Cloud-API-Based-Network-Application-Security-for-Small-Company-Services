# Stage 6 Vault Setup

Stage 6 configures Vault for lab secret management, per-tenant Transit keys,
AppRole service authentication, and PKI certificate issuance.

## Components

| File                                 | Purpose                                             |
| ------------------------------------ | --------------------------------------------------- |
| `scripts/vault-init.sh`              | Idempotent Vault bootstrap for dev mode             |
| `vault/policies/*.hcl`               | Least-privilege service policies                    |
| `shared/vault_client.py`             | Python wrapper for KV v2, Transit, AppRole, and PKI |
| `tests/test_vault_client.py`         | Unit tests for the wrapper                          |
| `runbooks/vault-production-notes.md` | Production limitations and hardening path           |

## Bootstrap

```powershell
docker compose up -d vault
bash scripts/vault-init.sh
```

The script prints AppRole values for each service. Copy only the role used by a
local service into `.env` as `VAULT_ROLE_ID` and `VAULT_SECRET_ID`.

## Smoke Tests

```powershell
docker compose exec -T -e VAULT_TOKEN=root-token-for-lab-only vault vault kv get secret/keycloak/admin_password

$PLAINTEXT = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("hello-alpha"))
$CIPHERTEXT = docker compose exec -T -e VAULT_TOKEN=root-token-for-lab-only vault vault write -field=ciphertext transit/encrypt/tenant-11111111-1111-1111-1111-111111111111 plaintext="$PLAINTEXT"
docker compose exec -T -e VAULT_TOKEN=root-token-for-lab-only vault vault write transit/decrypt/tenant-11111111-1111-1111-1111-111111111111 ciphertext="$CIPHERTEXT"
```

## Python Tests

```powershell
pytest tests/test_vault_client.py -v
```

## Notes

- Vault dev mode is lab-only.
- Service code should use AppRole bootstrap credentials, not the root token.
- KV v2 API paths use mount point `secret` and logical paths such as
  `services/resource-service/db_password`.
