#!/bin/bash
set -euo pipefail

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

BASE_URL="${1:-${PUBLIC_BASE_URL:-}}"
if [[ -z "$BASE_URL" ]]; then
  if [[ -n "${PUBLIC_DOMAIN:-}" ]]; then
    BASE_URL="https://${PUBLIC_DOMAIN}"
  else
    BASE_URL="https://localhost:${KONG_PROXY_HTTPS_PORT:-8443}"
  fi
fi
BASE_URL="${BASE_URL%/}"
PASSWORD="${KEYCLOAK_LAB_USER_PASSWORD:-TestPass123!}"
REDIS_PASSWORD="${REDIS_PASSWORD:-changeme-redis}"

section() {
  printf "\n==== %s ====\n" "$1"
}

http_status() {
  curl -k -s -o /dev/null -w "%{http_code}" "$@"
}

json_value() {
  local expression="$1"
  python - "$expression" <<'PY'
import json
import sys

expression = sys.argv[1]
data = json.load(sys.stdin)
value = data
for part in expression.split("."):
    value = value[part]
print(value)
PY
}

section "Acquire lab tokens"
ALPHA_TOKEN="$(bash scripts/get-token.sh alpha-user@example.com "$PASSWORD")"
BETA_TOKEN="$(bash scripts/get-token.sh beta-user@example.com "$PASSWORD")"
echo "alpha token length: ${#ALPHA_TOKEN}"
echo "beta token length: ${#BETA_TOKEN}"

section "Gateway rejects unauthenticated request"
status="$(http_status "$BASE_URL/api/v1/resources")"
echo "GET /api/v1/resources without token -> $status"

section "Alpha lists resources"
curl -k -s "$BASE_URL/api/v1/resources" -H "Authorization: Bearer $ALPHA_TOKEN" | python -m json.tool

section "Alpha creates a resource"
RESOURCE_BODY="$(python - <<'PY'
import json
import uuid
print(json.dumps({
    "name": "internet-demo-" + uuid.uuid4().hex[:12],
    "data": {"classification": "confidential", "demo": "internet"},
    "url": "https://example.com/report"
}, separators=(",", ":")))
PY
)"

CREATE_RESPONSE="$(curl -k -s -X POST "$BASE_URL/api/v1/resources" \
  -H "Authorization: Bearer $ALPHA_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary "$RESOURCE_BODY")"
printf "%s\n" "$CREATE_RESPONSE" | python -m json.tool
RESOURCE_ID="$(printf "%s\n" "$CREATE_RESPONSE" | json_value id)"
echo "created resource_id=$RESOURCE_ID"

section "Beta attempts cross-tenant BOLA read"
BETA_STATUS="$(http_status "$BASE_URL/api/v1/resources/$RESOURCE_ID" -H "Authorization: Bearer $BETA_TOKEN")"
echo "beta GET alpha resource -> $BETA_STATUS"

section "Tenant user is denied admin route"
ADMIN_STATUS="$(http_status "$BASE_URL/api/v1/admin/tenants" -H "Authorization: Bearer $ALPHA_TOKEN")"
echo "alpha user GET admin tenants -> $ADMIN_STATUS"

section "WAF-lite rejects non-json write"
WAF_STATUS="$(http_status -X POST "$BASE_URL/api/v1/resources" -H "Authorization: Bearer $ALPHA_TOKEN" -d '{"name":"bad-content-type"}')"
echo "POST without application/json -> $WAF_STATUS"

section "Rate limiting returns 429"
docker compose exec -T redis redis-cli -a "$REDIS_PASSWORD" FLUSHDB >/dev/null 2>&1 || true
for _ in $(seq 1 25); do
  http_status "$BASE_URL/api/v1/resources" -H "Authorization: Bearer $ALPHA_TOKEN"
  printf "\n"
done | sort | uniq -c

section "Forged Stripe webhook is rejected"
WEBHOOK_STATUS="$(http_status -X POST "$BASE_URL/webhooks/stripe" \
  -H "Content-Type: application/json" \
  -H "Stripe-Signature: t=123,v1=forged" \
  --data-binary @demo/synthetic-data/stripe-payment-succeeded.json)"
echo "forged webhook -> $WEBHOOK_STATUS"

section "ML-DSA sign/verify and tamper check"
python - <<'PY'
from shared.pqc_signing import MLDSAKeyPair, MLDSASigner
from shared.s2s_token import S2STokenError, create_s2s_token, verify_s2s_token

signer = MLDSASigner.from_keypair(MLDSAKeyPair.generate())
token = create_s2s_token(
    signer=signer,
    issuer="payment-service",
    subject="payment-service",
    audience="resource-service",
    tenant_id="11111111-1111-1111-1111-111111111111",
    now=1000,
)
claims = verify_s2s_token(
    token,
    signer=signer,
    expected_audience="resource-service",
    allowed_issuers=["payment-service"],
    now=1001,
)
print("valid token tenant_id:", claims["tenant_id"])
tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
try:
    verify_s2s_token(
        tampered,
        signer=signer,
        expected_audience="resource-service",
        allowed_issuers=["payment-service"],
        now=1001,
    )
except S2STokenError as exc:
    print("tampered token rejected:", exc)
PY

section "Demo complete"
echo "Now show Grafana/Loki for security.bola_attempt and security.invalid_webhook_signature."
