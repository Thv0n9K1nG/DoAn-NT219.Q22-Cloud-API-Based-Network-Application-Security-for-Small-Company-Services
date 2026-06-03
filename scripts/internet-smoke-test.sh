#!/bin/bash
set -euo pipefail

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

BASE_URL="${PUBLIC_BASE_URL:-${1:-}}"
if [[ -z "$BASE_URL" ]]; then
  if [[ -n "${PUBLIC_DOMAIN:-}" ]]; then
    BASE_URL="https://${PUBLIC_DOMAIN}"
  else
    BASE_URL="https://localhost:${KONG_PROXY_HTTPS_PORT:-8443}"
  fi
fi
BASE_URL="${BASE_URL%/}"

http_status() {
  curl -k -s -o /dev/null -w "%{http_code}" "$@"
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

ALPHA_TOKEN="$(bash scripts/get-token.sh alpha-user@example.com "${KEYCLOAK_LAB_USER_PASSWORD:-TestPass123!}")"

assert_status "gateway rejects missing token" "401" "$BASE_URL/api/v1/resources"
assert_status "tenant user lists resources" "200" "$BASE_URL/api/v1/resources" -H "Authorization: Bearer $ALPHA_TOKEN"
assert_status "tenant user denied admin route" "403" "$BASE_URL/api/v1/admin/tenants" -H "Authorization: Bearer $ALPHA_TOKEN"
assert_status "non-json write rejected" "415" -X POST "$BASE_URL/api/v1/resources" -H "Authorization: Bearer $ALPHA_TOKEN" -d '{"name":"bad"}'
assert_status "forged Stripe webhook rejected" "400" -X POST "$BASE_URL/webhooks/stripe" -H "Content-Type: application/json" -H "Stripe-Signature: t=123,v1=forged" -d '{"id":"evt_forged","type":"payment_intent.succeeded","data":{"object":{"id":"pi_forged"}}}'

echo "Internet smoke test passed."
