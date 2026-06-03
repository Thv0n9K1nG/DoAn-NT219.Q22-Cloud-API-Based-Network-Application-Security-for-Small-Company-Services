#!/bin/bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <tenant-name> <admin-email> [admin-password]" >&2
  exit 2
fi

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

TENANT_NAME="$1"
ADMIN_EMAIL="$2"
ADMIN_PASSWORD="${3:-${KEYCLOAK_LAB_USER_PASSWORD:-TestPass123!}}"
TENANT_ID="${TENANT_ID:-$(python - <<'PY'
import uuid
print(uuid.uuid4())
PY
)}"

REALM="${KEYCLOAK_REALM:-saas-platform}"
KEYCLOAK_ADMIN_USER="${KEYCLOAK_ADMIN:-admin}"
KEYCLOAK_ADMIN_PASSWORD="${KEYCLOAK_ADMIN_PASSWORD:-changeme-keycloak-admin}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
VAULT_DEV_TOKEN="${VAULT_DEV_TOKEN:-root-token-for-lab-only}"
VAULT_ADDR_IN_CONTAINER="${VAULT_ADDR_IN_CONTAINER:-http://127.0.0.1:8200}"
KC="/opt/keycloak/bin/kcadm.sh"

kc() {
  docker compose exec -T keycloak "$KC" "$@"
}

vault_cmd() {
  docker compose exec -T \
    -e VAULT_ADDR="$VAULT_ADDR_IN_CONTAINER" \
    -e VAULT_TOKEN="$VAULT_DEV_TOKEN" \
    vault vault "$@"
}

upsert_tenant_db() {
  local db="$1"
  docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$db" \
    -v tenant_id="$TENANT_ID" -v tenant_name="$TENANT_NAME" <<'SQL'
INSERT INTO tenants (id, name, status)
VALUES (:'tenant_id'::uuid, :'tenant_name', 'active')
ON CONFLICT (id) DO UPDATE
SET name = EXCLUDED.name,
    status = EXCLUDED.status,
    updated_at = now();
SQL
}

echo "Authenticating to Keycloak admin API..."
kc config credentials --server http://localhost:8080 --realm master --user "$KEYCLOAK_ADMIN_USER" --password "$KEYCLOAK_ADMIN_PASSWORD" >/dev/null

echo "Creating/updating tenant records in service databases..."
for db in userdb resourcedb admindb paymentdb; do
  upsert_tenant_db "$db" >/dev/null
done

echo "Creating Vault transit key tenant-$TENANT_ID..."
if vault_cmd read "transit/keys/tenant-$TENANT_ID" >/dev/null 2>&1; then
  echo "Vault transit key already exists."
else
  vault_cmd write -f "transit/keys/tenant-$TENANT_ID" >/dev/null
fi

echo "Creating/updating Keycloak admin user $ADMIN_EMAIL..."
USER_ID="$(kc get users -r "$REALM" -q username="$ADMIN_EMAIL" --fields id --format csv --noquotes 2>/dev/null | tail -n 1 | tr -d '\r')"
if [[ -z "$USER_ID" ]]; then
  kc create users -r "$REALM" \
    -s username="$ADMIN_EMAIL" \
    -s email="$ADMIN_EMAIL" \
    -s enabled=true \
    -s emailVerified=true \
    -s "attributes.tenant_id=[\"$TENANT_ID\"]" \
    -s "attributes.org_name=[\"$TENANT_NAME\"]" >/dev/null
else
  kc update "users/$USER_ID" -r "$REALM" \
    -s email="$ADMIN_EMAIL" \
    -s enabled=true \
    -s emailVerified=true \
    -s "attributes.tenant_id=[\"$TENANT_ID\"]" \
    -s "attributes.org_name=[\"$TENANT_NAME\"]" >/dev/null
fi

kc set-password -r "$REALM" --username "$ADMIN_EMAIL" --new-password "$ADMIN_PASSWORD" --temporary=false >/dev/null
for role in tenant_admin read:users write:users read:resources write:resources read:billing write:billing; do
  kc add-roles -r "$REALM" --uusername "$ADMIN_EMAIL" --rolename "$role" >/dev/null 2>&1 || true
done

echo
echo "Tenant onboarded:"
echo "  tenant_id=$TENANT_ID"
echo "  tenant_name=$TENANT_NAME"
echo "  admin_email=$ADMIN_EMAIL"
echo "  vault_transit_key=tenant-$TENANT_ID"
echo
echo "Next: create service data/users for this tenant and run a token claim smoke test."
