#!/bin/bash
set -euo pipefail

REALM="${KEYCLOAK_REALM:-saas-platform}"
ADMIN_USER="${KEYCLOAK_ADMIN:-admin}"
ADMIN_PASSWORD="${KEYCLOAK_ADMIN_PASSWORD:-changeme-keycloak-admin}"
LAB_PASSWORD="${KEYCLOAK_LAB_USER_PASSWORD:-TestPass123!}"
KC="/opt/keycloak/bin/kcadm.sh"

kc() {
  docker compose exec -T keycloak "$KC" "$@"
}

wait_for_keycloak() {
  echo "Waiting for Keycloak admin API..."
  for _ in $(seq 1 90); do
    if kc config credentials --server http://localhost:8080 --realm master --user "$ADMIN_USER" --password "$ADMIN_PASSWORD" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done

  echo "Keycloak did not become ready in time" >&2
  return 1
}

ensure_realm() {
  if kc get "realms/$REALM" >/dev/null 2>&1; then
    kc update "realms/$REALM" \
      -s enabled=true \
      -s accessTokenLifespan=900 \
      -s ssoSessionIdleTimeout=1800 \
      -s ssoSessionMaxLifespan=86400 \
      -s revokeRefreshToken=true \
      -s refreshTokenMaxReuse=0 >/dev/null
  else
    kc create realms \
      -s realm="$REALM" \
      -s enabled=true \
      -s displayName="Small Company SaaS Platform" \
      -s accessTokenLifespan=900 \
      -s ssoSessionIdleTimeout=1800 \
      -s ssoSessionMaxLifespan=86400 \
      -s revokeRefreshToken=true \
      -s refreshTokenMaxReuse=0 >/dev/null
  fi
}

ensure_role() {
  local role="$1"
  if ! kc get "roles/$role" -r "$REALM" >/dev/null 2>&1; then
    kc create roles -r "$REALM" -s name="$role" >/dev/null
  fi
}

client_id() {
  local client="$1"
  kc get clients -r "$REALM" -q clientId="$client" --fields id --format csv --noquotes 2>/dev/null | tail -n 1 | tr -d '\r'
}

delete_mapper_if_exists() {
  local client_uuid="$1"
  local mapper_name="$2"
  local mapper_id

  mapper_id="$(kc get "clients/$client_uuid/protocol-mappers/models" -r "$REALM" --fields id,name --format csv --noquotes 2>/dev/null | awk -F, -v name="$mapper_name" '$2 == name {print $1; exit}' | tr -d '\r')"
  if [[ -n "$mapper_id" ]]; then
    kc delete "clients/$client_uuid/protocol-mappers/models/$mapper_id" -r "$REALM" >/dev/null
  fi
}

ensure_user_attribute_mapper() {
  local client_uuid="$1"
  local mapper_name="$2"
  local attribute_name="$3"

  delete_mapper_if_exists "$client_uuid" "$mapper_name"
  kc create "clients/$client_uuid/protocol-mappers/models" -r "$REALM" \
    -s name="$mapper_name" \
    -s protocol=openid-connect \
    -s protocolMapper=oidc-usermodel-attribute-mapper \
    -s 'config."id.token.claim"=false' \
    -s 'config."access.token.claim"=true' \
    -s 'config."userinfo.token.claim"=true' \
    -s "config.\"user.attribute\"=$attribute_name" \
    -s "config.\"claim.name\"=$mapper_name" \
    -s 'config."jsonType.label"=String' >/dev/null 2>&1
}

ensure_audience_mapper() {
  local client_uuid="$1"

  delete_mapper_if_exists "$client_uuid" audience-saas-api
  kc create "clients/$client_uuid/protocol-mappers/models" -r "$REALM" \
    -s name=audience-saas-api \
    -s protocol=openid-connect \
    -s protocolMapper=oidc-audience-mapper \
    -s 'config."id.token.claim"=false' \
    -s 'config."access.token.claim"=true' \
    -s 'config."included.custom.audience"=saas-api' >/dev/null 2>&1
}

ensure_public_client() {
  local client="$1"
  local redirect="$2"
  local web_origin="$3"
  local id

  id="$(client_id "$client")"
  if [[ -z "$id" ]]; then
    kc create clients -r "$REALM" \
      -s clientId="$client" \
      -s name="$client" \
      -s enabled=true \
      -s protocol=openid-connect \
      -s publicClient=true \
      -s standardFlowEnabled=true \
      -s directAccessGrantsEnabled=true \
      -s serviceAccountsEnabled=false \
      -s fullScopeAllowed=true \
      -s "redirectUris=[\"$redirect\"]" \
      -s "webOrigins=[\"$web_origin\"]" \
      -s 'attributes."pkce.code.challenge.method"=S256' >/dev/null
    id="$(client_id "$client")"
  else
    kc update "clients/$id" -r "$REALM" \
      -s enabled=true \
      -s publicClient=true \
      -s standardFlowEnabled=true \
      -s directAccessGrantsEnabled=true \
      -s serviceAccountsEnabled=false \
      -s fullScopeAllowed=true \
      -s "redirectUris=[\"$redirect\"]" \
      -s "webOrigins=[\"$web_origin\"]" \
      -s 'attributes."pkce.code.challenge.method"=S256' >/dev/null
  fi

  ensure_user_attribute_mapper "$id" tenant_id tenant_id
  ensure_user_attribute_mapper "$id" org_name org_name
  ensure_audience_mapper "$id"
}

ensure_confidential_client() {
  local client="$1"
  local secret="$2"
  local id

  id="$(client_id "$client")"
  if [[ -z "$id" ]]; then
    kc create clients -r "$REALM" \
      -s clientId="$client" \
      -s name="$client" \
      -s enabled=true \
      -s protocol=openid-connect \
      -s publicClient=false \
      -s clientAuthenticatorType=client-secret \
      -s secret="$secret" \
      -s standardFlowEnabled=false \
      -s directAccessGrantsEnabled=false \
      -s serviceAccountsEnabled=true \
      -s fullScopeAllowed=true >/dev/null
    id="$(client_id "$client")"
  else
    kc update "clients/$id" -r "$REALM" \
      -s enabled=true \
      -s publicClient=false \
      -s clientAuthenticatorType=client-secret \
      -s secret="$secret" \
      -s standardFlowEnabled=false \
      -s directAccessGrantsEnabled=false \
      -s serviceAccountsEnabled=true \
      -s fullScopeAllowed=true >/dev/null
  fi

  ensure_audience_mapper "$id"
}

user_id() {
  local username="$1"
  kc get users -r "$REALM" -q username="$username" --fields id --format csv --noquotes 2>/dev/null | tail -n 1 | tr -d '\r'
}

ensure_user() {
  local username="$1"
  local tenant_id="$2"
  local org_name="$3"
  shift 3
  local roles=("$@")
  local id

  id="$(user_id "$username")"
  if [[ -z "$id" ]]; then
    kc create users -r "$REALM" \
      -s username="$username" \
      -s email="$username" \
      -s enabled=true \
      -s emailVerified=true \
      -s "attributes.tenant_id=[\"$tenant_id\"]" \
      -s "attributes.org_name=[\"$org_name\"]" >/dev/null
  else
    kc update "users/$id" -r "$REALM" \
      -s email="$username" \
      -s enabled=true \
      -s emailVerified=true \
      -s "attributes.tenant_id=[\"$tenant_id\"]" \
      -s "attributes.org_name=[\"$org_name\"]" >/dev/null
  fi

  kc set-password -r "$REALM" --username "$username" --new-password "$LAB_PASSWORD" --temporary=false >/dev/null

  for role in "${roles[@]}"; do
    kc add-roles -r "$REALM" --uusername "$username" --rolename "$role" >/dev/null 2>&1 || true
  done
}

main() {
  wait_for_keycloak
  ensure_realm

  for role in \
    tenant_admin tenant_user platform_admin \
    read:users write:users delete:users \
    read:resources write:resources delete:resources \
    read:billing write:billing read:admin write:admin; do
    ensure_role "$role"
  done

  ensure_public_client saas-spa "http://localhost:3001/*" "http://localhost:3001"
  ensure_public_client saas-mobile "http://localhost:3002/*" "+"
  ensure_confidential_client saas-m2m "changeme-saas-m2m-secret"
  ensure_confidential_client kong-introspect "changeme-kong-introspect-secret"

  # User attributes simulate tenant organizations until the lab adopts Keycloak Organizations.
  ensure_user alpha-admin@example.com "11111111-1111-1111-1111-111111111111" tenant-alpha tenant_admin read:users write:users read:resources write:resources read:billing
  ensure_user alpha-user@example.com "11111111-1111-1111-1111-111111111111" tenant-alpha tenant_user read:resources write:resources
  ensure_user beta-admin@example.com "22222222-2222-2222-2222-222222222222" tenant-beta tenant_admin read:users write:users read:resources write:resources read:billing
  ensure_user beta-user@example.com "22222222-2222-2222-2222-222222222222" tenant-beta tenant_user read:resources write:resources
  ensure_user platform-admin@example.com "" platform platform_admin read:admin write:admin

  echo "Keycloak realm '$REALM' is ready."
}

main "$@"
