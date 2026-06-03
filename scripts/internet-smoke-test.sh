#!/bin/bash
set -euo pipefail

load_env_defaults() {
  local line key value
  [[ -f .env ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" == *"="* ]] || continue
    key="${line%%=*}"
    value="${line#*=}"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    if [[ -z "${!key+x}" ]]; then
      export "$key=$value"
    fi
  done < .env
}

load_env_defaults

BASE_URL="${PUBLIC_BASE_URL:-${1:-}}"
if [[ -z "$BASE_URL" ]]; then
  if [[ -n "${PUBLIC_DOMAIN:-}" ]]; then
    BASE_URL="https://${PUBLIC_DOMAIN}"
  else
    BASE_URL="https://localhost:${KONG_PROXY_HTTPS_PORT:-8443}"
  fi
fi
BASE_URL="${BASE_URL%/}"
REDIS_PASSWORD="${REDIS_PASSWORD:-changeme-redis}"

http_status() {
  local status
  status="$(curl -k -s -o /dev/null -w "%{http_code}" "$@" || true)"
  printf "%s" "${status:-000}"
}

assert_status() {
  local label="$1"
  local expected="$2"
  shift 2
  local actual
  actual="$(http_status "$@")"
  printf "%-48s expected=%s actual=%s\n" "$label" "$expected" "$actual"
  if [[ "$actual" != "$expected" ]]; then
    echo "FAILED: $label" >&2
    exit 1
  fi
}

echo "Smoke testing $BASE_URL"

docker compose exec -T redis redis-cli -a "$REDIS_PASSWORD" FLUSHDB >/dev/null 2>&1 || true

ALPHA_TOKEN="$(bash scripts/get-token.sh alpha-user@example.com "${KEYCLOAK_LAB_USER_PASSWORD:-TestPass123!}")"

assert_status "gateway rejects missing token" "401" "$BASE_URL/api/v1/resources"
assert_status "tenant user lists resources" "200" "$BASE_URL/api/v1/resources" -H "Authorization: Bearer $ALPHA_TOKEN"
assert_status "tenant user denied admin route" "403" "$BASE_URL/api/v1/admin/tenants" -H "Authorization: Bearer $ALPHA_TOKEN"
assert_status "non-json write rejected" "415" -X POST "$BASE_URL/api/v1/resources" -H "Authorization: Bearer $ALPHA_TOKEN" -d '{"name":"bad"}'
assert_status "forged Stripe webhook rejected" "400" -X POST "$BASE_URL/webhooks/stripe" -H "Content-Type: application/json" -H "Stripe-Signature: t=123,v1=forged" -d '{"id":"evt_forged","type":"payment_intent.succeeded","data":{"object":{"id":"pi_forged"}}}'

echo "Internet smoke test passed."
