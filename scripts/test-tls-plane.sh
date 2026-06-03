#!/bin/bash
set -euo pipefail

KONG_URL="${KONG_URL:-https://localhost:${KONG_PROXY_HTTPS_PORT:-8443}}"
REDIS_PASSWORD="${REDIS_PASSWORD:-changeme-redis}"

http_status() {
  curl -k -s -o /dev/null -w "%{http_code}" "$@"
}

echo "Preparing Stage 11 TLS plane test..."
bash scripts/generate-dev-certs.sh >/dev/null
docker compose up -d postgres redis vault keycloak opa >/dev/null
docker compose up -d --build --force-recreate user-service resource-service admin-service payment-service >/dev/null
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-postgres}" -d resourcedb < scripts/db-init.sql >/dev/null
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-postgres}" -d resourcedb < scripts/apply-rls.sql >/dev/null
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-postgres}" -d resourcedb < scripts/seed-data.sql >/dev/null
bash scripts/keycloak-init.sh >/dev/null
bash scripts/kong-init.sh >/dev/null
docker compose up -d --force-recreate kong >/dev/null

for _ in $(seq 1 60); do
  if docker compose exec -T kong kong health >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "External Kong TLS certificate:"
external_cert="$(openssl s_client -connect localhost:8443 -servername localhost </dev/null 2>/dev/null | openssl x509 -noout -subject -issuer)"
printf "%s\n" "$external_cert"
if ! printf "%s\n" "$external_cert" | grep -q "CN *= *localhost"; then
  echo "FAILED: Kong certificate subject should contain localhost" >&2
  exit 1
fi

echo "Verifying resource-service upstream certificate from Kong container..."
docker compose exec -T kong sh -c "openssl s_client -connect resource-service:8000 -servername resource-service -CAfile /etc/kong/certs/internal-ca.crt -verify_return_error </dev/null >/tmp/resource-service-tls.txt 2>&1 && grep -q 'Verify return code: 0 (ok)' /tmp/resource-service-tls.txt"
echo "resource-service upstream certificate verify: ok"

echo "Verifying resource-service rejects clients without a certificate..."
if docker compose exec -T kong sh -c "printf 'GET /health/live HTTP/1.1\r\nHost: resource-service\r\n\r\n' | openssl s_client -quiet -connect resource-service:8000 -servername resource-service -CAfile /etc/kong/certs/internal-ca.crt >/tmp/no-client-cert.txt 2>&1 && grep -q 'HTTP/1.1 200' /tmp/no-client-cert.txt"; then
  echo "FAILED: resource-service accepted a request without client certificate" >&2
  exit 1
fi
echo "resource-service rejects missing client certificate: ok"

echo "Verifying resource-service accepts Kong upstream client certificate..."
docker compose exec -T kong sh -c "printf 'GET /health/live HTTP/1.1\r\nHost: resource-service\r\n\r\n' | openssl s_client -quiet -connect resource-service:8000 -servername resource-service -cert /etc/kong/certs/kong-upstream-client.crt -key /etc/kong/certs/kong-upstream-client.key -CAfile /etc/kong/certs/internal-ca.crt >/tmp/with-client-cert.txt 2>&1 && grep -q 'HTTP/1.1 200' /tmp/with-client-cert.txt"
echo "resource-service accepts Kong client certificate: ok"

echo "Verifying resource-service rejects mTLS clients without ML-DSA assertion..."
docker compose exec -T kong sh -c "printf 'GET /api/v1/resources HTTP/1.1\r\nHost: resource-service\r\n\r\n' | openssl s_client -quiet -connect resource-service:8000 -servername resource-service -cert /etc/kong/certs/kong-upstream-client.crt -key /etc/kong/certs/kong-upstream-client.key -CAfile /etc/kong/certs/internal-ca.crt >/tmp/no-mldsa-assertion.txt 2>&1 && grep -q 'Missing ML-DSA upstream client assertion' /tmp/no-mldsa-assertion.txt"
echo "resource-service rejects mTLS without ML-DSA assertion: ok"

no_token_status="$(http_status "$KONG_URL/api/v1/resources")"
printf "%-42s expected=401 actual=%s\n" "external TLS no-token gateway request" "$no_token_status"
if [[ "$no_token_status" != "401" ]]; then
  echo "FAILED: expected no-token request to be rejected over TLS" >&2
  exit 1
fi

docker compose exec -T redis redis-cli -a "$REDIS_PASSWORD" FLUSHDB >/dev/null 2>&1 || true
ALPHA_TOKEN="$(bash scripts/get-token.sh alpha-user@example.com 'TestPass123!')"
resource_status="$(http_status "$KONG_URL/api/v1/resources" -H "Authorization: Bearer $ALPHA_TOKEN")"
printf "%-42s expected=200 actual=%s\n" "Kong routes with mTLS plus ML-DSA" "$resource_status"
if [[ "$resource_status" != "200" ]]; then
  echo "FAILED: expected Kong to route with HTTPS upstream and ML-DSA assertion" >&2
  exit 1
fi

echo "Stage 11 TLS plus ML-DSA plane test passed."
