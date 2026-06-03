#!/bin/bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <username-or-email>" >&2
  exit 2
fi

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

REALM="${KEYCLOAK_REALM:-saas-platform}"
ADMIN_USER="${KEYCLOAK_ADMIN:-admin}"
ADMIN_PASSWORD="${KEYCLOAK_ADMIN_PASSWORD:-changeme-keycloak-admin}"
USERNAME="$1"
KC="/opt/keycloak/bin/kcadm.sh"

kc() {
  docker compose exec -T keycloak "$KC" "$@"
}

echo "Authenticating to Keycloak admin API..."
kc config credentials --server http://localhost:8080 --realm master --user "$ADMIN_USER" --password "$ADMIN_PASSWORD" >/dev/null

USER_ID="$(kc get users -r "$REALM" -q username="$USERNAME" --fields id --format csv --noquotes 2>/dev/null | tail -n 1 | tr -d '\r')"
if [[ -z "$USER_ID" ]]; then
  USER_ID="$(kc get users -r "$REALM" -q email="$USERNAME" --fields id --format csv --noquotes 2>/dev/null | tail -n 1 | tr -d '\r')"
fi

if [[ -z "$USER_ID" ]]; then
  echo "User not found in realm $REALM: $USERNAME" >&2
  exit 1
fi

echo "Revoking sessions for $USERNAME ($USER_ID)..."
kc create "users/$USER_ID/logout" -r "$REALM" -n >/dev/null

echo "Remaining sessions:"
kc get "users/$USER_ID/sessions" -r "$REALM" || true

echo "Session revocation request completed."
