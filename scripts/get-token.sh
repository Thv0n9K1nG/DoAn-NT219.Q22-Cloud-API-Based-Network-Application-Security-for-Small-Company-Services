#!/bin/bash
set -euo pipefail

USERNAME="${1:-alpha-user@example.com}"
PASSWORD="${2:-TestPass123!}"
CLIENT_ID="${3:-saas-spa}"
KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:${KEYCLOAK_HOST_PORT:-18080}}"
REALM="${KEYCLOAK_REALM:-saas-platform}"

# Password grant is enabled only for local lab automation; production clients use Authorization Code + PKCE.
response="$(curl -fsS -X POST "$KEYCLOAK_URL/realms/$REALM/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=$CLIENT_ID" \
  -d "username=$USERNAME" \
  -d "password=$PASSWORD" \
  -d "scope=openid profile email")"

if command -v jq >/dev/null 2>&1; then
  echo "$response" | jq -r '.access_token'
elif command -v python3 >/dev/null 2>&1; then
  TOKEN_RESPONSE="$response" python3 - <<'PY'
import json
import os

print(json.loads(os.environ["TOKEN_RESPONSE"])["access_token"])
PY
elif command -v python >/dev/null 2>&1; then
  TOKEN_RESPONSE="$response" python - <<'PY'
import json
import os

print(json.loads(os.environ["TOKEN_RESPONSE"])["access_token"])
PY
else
  printf '%s' "$response" | sed -n 's/.*"access_token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p'
fi
