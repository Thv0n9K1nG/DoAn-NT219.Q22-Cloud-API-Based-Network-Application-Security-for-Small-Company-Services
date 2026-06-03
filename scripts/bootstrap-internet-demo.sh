#!/bin/bash
set -euo pipefail

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

VAULT_HOST_ADDR="${VAULT_HOST_ADDR:-http://localhost:${VAULT_HOST_PORT:-8200}}"
VAULT_TOKEN="${VAULT_TOKEN:-${VAULT_DEV_TOKEN:-root-token-for-lab-only}}"

echo "=== 1. Generate lab TLS certificates ==="
bash scripts/generate-dev-certs.sh

echo "=== 2. Start infrastructure ==="
docker compose up -d postgres redis vault

echo "=== 3. Initialize Vault and ML-DSA keys ==="
bash scripts/vault-init.sh
python scripts/generate_mldsa_keys.py --vault-addr "$VAULT_HOST_ADDR" --vault-token "$VAULT_TOKEN"

echo "=== 4. Start Keycloak and OPA ==="
docker compose up -d keycloak opa
bash scripts/keycloak-init.sh

echo "=== 5. Build and start microservices ==="
docker compose up -d --build user-service resource-service admin-service payment-service

echo "=== 6. Apply database schemas and seed data ==="
bash scripts/apply-lab-schemas.sh

echo "=== 7. Render Kong config and start gateway/observability ==="
bash scripts/kong-init.sh
docker compose --profile observability up -d --build kong loki grafana promtail

if [[ -n "${PUBLIC_DOMAIN:-}" ]]; then
  echo "=== 8. Start Caddy public HTTPS proxy for $PUBLIC_DOMAIN ==="
  docker compose -f docker-compose.yml -f deploy/docker-compose.caddy.yml --profile observability up -d caddy
else
  echo "PUBLIC_DOMAIN is not set; skipping Caddy. Set PUBLIC_DOMAIN in .env for Internet HTTPS."
fi

echo "=== 9. Container status ==="
docker compose ps

echo
echo "Bootstrap complete."
echo "Local Kong HTTPS: https://localhost:${KONG_PROXY_HTTPS_PORT:-8443}"
if [[ -n "${PUBLIC_DOMAIN:-}" ]]; then
  echo "Public API URL: https://${PUBLIC_DOMAIN}"
fi
