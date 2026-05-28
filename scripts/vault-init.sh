#!/bin/bash
set -euo pipefail

VAULT_DEV_TOKEN="${VAULT_DEV_TOKEN:-root-token-for-lab-only}"
VAULT_ADDR_IN_CONTAINER="${VAULT_ADDR_IN_CONTAINER:-http://127.0.0.1:8200}"
PKI_ROLE="${VAULT_PKI_ROLE:-internal-services}"

TENANT_ALPHA="11111111-1111-1111-1111-111111111111"
TENANT_BETA="22222222-2222-2222-2222-222222222222"

vault_cmd() {
  docker compose exec -T \
    -e VAULT_ADDR="$VAULT_ADDR_IN_CONTAINER" \
    -e VAULT_TOKEN="$VAULT_DEV_TOKEN" \
    vault vault "$@"
}

wait_for_vault() {
  echo "Waiting for Vault..."
  for _ in $(seq 1 60); do
    if vault_cmd status >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done

  echo "Vault did not become ready in time" >&2
  return 1
}

enable_secret_engine() {
  local path="$1"
  local engine="$2"

  if vault_cmd secrets list -format=json | grep -q "\"$path/\""; then
    echo "Secret engine already enabled: $path/"
  else
    echo "Enabling secret engine: $path/ ($engine)"
    vault_cmd secrets enable -path="$path" "$engine" >/dev/null
  fi
}

enable_auth_method() {
  local path="$1"
  local method="$2"

  if vault_cmd auth list -format=json | grep -q "\"$path/\""; then
    echo "Auth method already enabled: $path/"
  else
    echo "Enabling auth method: $path/ ($method)"
    vault_cmd auth enable -path="$path" "$method" >/dev/null
  fi
}

put_kv() {
  local path="$1"
  shift
  vault_cmd kv put "$path" "$@" >/dev/null
}

ensure_transit_key() {
  local key_name="$1"
  if vault_cmd read "transit/keys/$key_name" >/dev/null 2>&1; then
    echo "Transit key already exists: $key_name"
  else
    echo "Creating transit key: $key_name"
    vault_cmd write -f "transit/keys/$key_name" >/dev/null
  fi
}

write_policy() {
  local service="$1"
  docker compose exec -T \
    -e VAULT_ADDR="$VAULT_ADDR_IN_CONTAINER" \
    -e VAULT_TOKEN="$VAULT_DEV_TOKEN" \
    vault vault policy write "$service" - < "vault/policies/$service.hcl" >/dev/null
}

ensure_approle() {
  local service="$1"
  vault_cmd write "auth/approle/role/$service" \
    token_policies="$service" \
    token_ttl="1h" \
    token_max_ttl="4h" \
    secret_id_ttl="24h" \
    secret_id_num_uses="20" >/dev/null
}

print_approle_env() {
  local service="$1"
  local prefix="$2"
  local role_id
  local secret_id

  role_id="$(vault_cmd read -field=role_id "auth/approle/role/$service/role-id")"
  secret_id="$(vault_cmd write -field=secret_id -f "auth/approle/role/$service/secret-id")"

  echo "${prefix}_VAULT_ROLE_ID=$role_id"
  echo "${prefix}_VAULT_SECRET_ID=$secret_id"
}

configure_pki() {
  if ! vault_cmd read pki/cert/ca >/dev/null 2>&1; then
    echo "Generating lab root CA for Vault PKI"
    vault_cmd write -field=certificate pki/root/generate/internal \
      common_name="nt219-lab.internal" \
      ttl="8760h" >/dev/null
  fi

  vault_cmd write pki/config/urls \
    issuing_certificates="$VAULT_ADDR_IN_CONTAINER/v1/pki/ca" \
    crl_distribution_points="$VAULT_ADDR_IN_CONTAINER/v1/pki/crl" >/dev/null

  vault_cmd write "pki/roles/$PKI_ROLE" \
    allowed_domains="service.local,internal,localhost" \
    allow_subdomains=true \
    allow_bare_domains=true \
    allow_localhost=true \
    allow_ip_sans=true \
    max_ttl="720h" >/dev/null
}

main() {
  wait_for_vault

  enable_secret_engine secret kv-v2
  enable_secret_engine transit transit
  enable_secret_engine pki pki
  enable_secret_engine database database
  enable_auth_method approle approle

  configure_pki

  ensure_transit_key "tenant-$TENANT_ALPHA"
  ensure_transit_key "tenant-$TENANT_BETA"

  # Lab secrets are deterministic placeholders; production values must be injected out of band.
  put_kv secret/keycloak/admin_password value="${KEYCLOAK_ADMIN_PASSWORD:-changeme-keycloak-admin}"
  put_kv secret/keycloak/saas-m2m/secret value="${SAAS_M2M_CLIENT_SECRET:-changeme-saas-m2m-secret}"
  put_kv secret/stripe/secret_key value="${STRIPE_SECRET_KEY:-sk_test_lab_placeholder}"
  put_kv secret/stripe/webhook_secret value="${STRIPE_WEBHOOK_SECRET:-whsec_lab_placeholder}"
  put_kv secret/database/postgres_password value="${POSTGRES_PASSWORD:-changeme-postgres}"
  put_kv secret/services/user-service/db_password value="${USER_SVC_DB_PASSWORD:-changeme-user-db}"
  put_kv secret/services/resource-service/db_password value="${RESOURCE_SVC_DB_PASSWORD:-changeme-resource-db}"
  put_kv secret/services/payment-service/db_password value="${PAYMENT_SVC_DB_PASSWORD:-changeme-payment-db}"
  put_kv secret/services/admin-service/db_password value="${ADMIN_SVC_DB_PASSWORD:-changeme-admin-db}"
  put_kv secret/pqc/s2s-signing \
    algorithm="ML-DSA-65" \
    public_key="lab-public-key-placeholder" \
    private_key="lab-private-key-placeholder"
  put_kv secret/pqc/webhook-signing \
    algorithm="ML-DSA-65" \
    public_key="lab-webhook-public-key-placeholder" \
    private_key="lab-webhook-private-key-placeholder"

  for service in user-service resource-service payment-service admin-service; do
    write_policy "$service"
    ensure_approle "$service"
  done

  echo
  echo "Copy these AppRole bootstrap values into .env for local service tests:"
  print_approle_env user-service USER_SVC
  print_approle_env resource-service RESOURCE_SVC
  print_approle_env payment-service PAYMENT_SVC
  print_approle_env admin-service ADMIN_SVC
}

main "$@"
