#!/bin/bash
set -euo pipefail

REALM="${KEYCLOAK_REALM:-saas-platform}"
KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:${KEYCLOAK_HOST_PORT:-18080}}"
KONG_JWT_ISSUER="${JWT_ISSUER:-${KEYCLOAK_URL%/}/realms/$REALM}"
REDIS_PASSWORD="${REDIS_PASSWORD:-changeme-redis}"
TEMPLATE="${KONG_TEMPLATE:-gateway/kong.template.yml}"
OUTPUT="${KONG_CONFIG:-gateway/kong.yml}"
PYTHON_BIN="${PYTHON_BIN:-}"

detect_python() {
  if [[ -n "$PYTHON_BIN" ]]; then
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=python3
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN=python
    return 0
  fi

  echo "python3 or python is required to render Kong configuration" >&2
  return 1
}

wait_for_keycloak_realm() {
  echo "Waiting for Keycloak realm metadata..."
  for _ in $(seq 1 90); do
    if curl -fsS "${KEYCLOAK_URL%/}/realms/$REALM" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done

  echo "Keycloak realm metadata did not become available" >&2
  return 1
}

render_kong_config() {
  if [[ ! -f gateway/certs/internal-ca.crt ]]; then
    echo "gateway/certs/internal-ca.crt is missing; generating lab certificates first..."
    bash scripts/generate-dev-certs.sh >/dev/null
  fi
  if [[ ! -f gateway/certs/kong-upstream-client.crt || ! -f gateway/certs/kong-upstream-client.key ]]; then
    echo "Kong upstream client certificate is missing; generating lab certificates first..."
    bash scripts/generate-dev-certs.sh >/dev/null
  fi
  if [[ ! -f gateway/certs/mldsa-upstream-client.token || ! -f gateway/certs/mldsa-upstream-client.pub ]]; then
    echo "Kong ML-DSA upstream client assertion is missing; generating lab certificates first..."
    bash scripts/generate-dev-certs.sh >/dev/null
  fi

  "$PYTHON_BIN" - "$TEMPLATE" "$OUTPUT" "$KEYCLOAK_URL" "$REALM" "$KONG_JWT_ISSUER" "$REDIS_PASSWORD" <<'PY'
import json
import sys
import urllib.request

template_path, output_path, keycloak_url, realm, issuer, redis_password = sys.argv[1:]
realm_url = f"{keycloak_url.rstrip('/')}/realms/{realm}"
with urllib.request.urlopen(realm_url, timeout=15) as response:
    realm_metadata = json.load(response)

public_key = realm_metadata["public_key"]
pem_lines = ["-----BEGIN PUBLIC KEY-----"]
pem_lines.extend(public_key[index:index + 64] for index in range(0, len(public_key), 64))
pem_lines.append("-----END PUBLIC KEY-----")
indented_pem = "\n".join(f"          {line}" for line in pem_lines)

with open("gateway/certs/internal-ca.crt", "r", encoding="utf-8") as file:
    internal_ca = "\n".join(f"      {line}" for line in file.read().splitlines())

with open("gateway/certs/kong-upstream-client.crt", "r", encoding="utf-8") as file:
    upstream_client_cert = "\n".join(f"      {line}" for line in file.read().splitlines())

with open("gateway/certs/kong-upstream-client.key", "r", encoding="utf-8") as file:
    upstream_client_key = "\n".join(f"      {line}" for line in file.read().splitlines())

with open("gateway/certs/mldsa-upstream-client.token", "r", encoding="ascii") as file:
    upstream_mldsa_token = file.read().strip()

with open(template_path, "r", encoding="utf-8") as file:
    rendered = file.read()

rendered = rendered.replace("__KONG_JWT_ISSUER__", issuer)
rendered = rendered.replace("__KONG_JWT_PUBLIC_KEY__", indented_pem)
rendered = rendered.replace("__KONG_INTERNAL_CA_CERT__", internal_ca)
rendered = rendered.replace("__KONG_UPSTREAM_CLIENT_CERT__", upstream_client_cert)
rendered = rendered.replace("__KONG_UPSTREAM_CLIENT_KEY__", upstream_client_key)
rendered = rendered.replace("__KONG_INTERNAL_MLDSA_TOKEN__", upstream_mldsa_token)
rendered = rendered.replace("__REDIS_PASSWORD__", redis_password)

with open(output_path, "w", encoding="utf-8", newline="\n") as file:
    file.write(rendered)
PY
}

wait_for_keycloak_realm
detect_python
render_kong_config
echo "Rendered $OUTPUT for issuer $KONG_JWT_ISSUER"
