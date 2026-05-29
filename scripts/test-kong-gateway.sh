#!/bin/bash
set -euo pipefail

KONG_URL="${KONG_URL:-https://localhost:${KONG_PROXY_HTTPS_PORT:-8443}}"
REDIS_PASSWORD="${REDIS_PASSWORD:-changeme-redis}"

apply_resource_schema() {
  docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-postgres}" -d resourcedb < scripts/db-init.sql >/dev/null
  docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-postgres}" -d resourcedb < scripts/apply-rls.sql >/dev/null
  docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-postgres}" -d resourcedb < scripts/seed-data.sql >/dev/null
}

http_status() {
  curl -k -s -o /dev/null -w "%{http_code}" "$@"
}

assert_status() {
  local name="$1"
  local expected="$2"
  shift 2
  local actual
  actual="$(http_status "$@")"
  printf "%-42s expected=%s actual=%s\n" "$name" "$expected" "$actual"
  if [[ "$actual" != "$expected" ]]; then
    echo "FAILED: $name" >&2
    exit 1
  fi
}

echo "Preparing Stage 10 gateway smoke test..."
bash scripts/generate-dev-certs.sh >/dev/null
docker compose up -d postgres redis vault keycloak opa >/dev/null
docker compose up -d --force-recreate user-service resource-service admin-service payment-service >/dev/null
apply_resource_schema
bash scripts/keycloak-init.sh >/dev/null
bash scripts/kong-init.sh >/dev/null
docker compose up -d --force-recreate kong >/dev/null

for _ in $(seq 1 60); do
  if docker compose exec -T kong kong health >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

ALPHA_TOKEN="$(bash scripts/get-token.sh alpha-user@example.com 'TestPass123!')"

assert_status "no token is rejected by gateway" "401" \
  "$KONG_URL/api/v1/resources"

assert_status "tenant user can list resources" "200" \
  "$KONG_URL/api/v1/resources" \
  -H "Authorization: Bearer $ALPHA_TOKEN"

assert_status "tenant user is denied admin route by OPA" "403" \
  "$KONG_URL/api/v1/admin/tenants" \
  -H "Authorization: Bearer $ALPHA_TOKEN"

assert_status "non-json API write is rejected" "415" \
  -X POST "$KONG_URL/api/v1/resources" \
  -H "Authorization: Bearer $ALPHA_TOKEN" \
  -d '{"name":"bad-content-type","data":{}}'

webhook_status="$(http_status -X POST "$KONG_URL/webhooks/stripe" -H "Content-Type: application/json" -d '{}')"
printf "%-42s expected=not-401 actual=%s\n" "stripe webhook route bypasses JWT" "$webhook_status"
if [[ "$webhook_status" == "401" ]]; then
  echo "FAILED: webhook route should not require Kong JWT" >&2
  exit 1
fi

# Reset only the lab Redis DB so rate-limit assertions are deterministic.
docker compose exec -T redis redis-cli -a "$REDIS_PASSWORD" FLUSHDB >/dev/null 2>&1 || true

rate_statuses="$(
  for _ in $(seq 1 25); do
    http_status "$KONG_URL/api/v1/resources" -H "Authorization: Bearer $ALPHA_TOKEN"
    printf "\n"
  done
)"

rate_summary="$(printf "%s\n" "$rate_statuses" | sort | uniq -c)"
printf "rate limit status summary:\n%s\n" "$rate_summary"
if ! printf "%s\n" "$rate_statuses" | grep -q "^429$"; then
  echo "FAILED: expected at least one 429 from Kong rate limiting" >&2
  exit 1
fi

echo "Stage 10 Kong gateway smoke test passed."
