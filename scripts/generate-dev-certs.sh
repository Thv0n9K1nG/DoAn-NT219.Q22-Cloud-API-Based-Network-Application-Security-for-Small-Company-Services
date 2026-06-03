#!/bin/bash
set -euo pipefail

CERT_DAYS="${CERT_DAYS:-365}"
CA_DIR="gateway/certs"
CA_KEY="$CA_DIR/internal-ca.key"
CA_CERT="$CA_DIR/internal-ca.crt"
KONG_KEY="$CA_DIR/kong.key"
KONG_CERT="$CA_DIR/kong.crt"
KONG_UPSTREAM_CLIENT_KEY="$CA_DIR/kong-upstream-client.key"
KONG_UPSTREAM_CLIENT_CERT="$CA_DIR/kong-upstream-client.crt"
KONG_MLDSA_PRIVATE="$CA_DIR/mldsa-upstream-client.key"
KONG_MLDSA_PUBLIC="$CA_DIR/mldsa-upstream-client.pub"
KONG_MLDSA_TOKEN="$CA_DIR/mldsa-upstream-client.token"
PYTHON_BIN="${PYTHON_BIN:-}"

mkdir -p "$CA_DIR"

detect_python() {
  if [[ -n "$PYTHON_BIN" ]]; then
    return 0
  fi

  local candidate
  for candidate in python.exe py.exe python3 python py; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "import pqcrypto" >/dev/null 2>&1; then
      PYTHON_BIN="$candidate"
      return 0
    fi
  done

  echo "A Python interpreter with pqcrypto is required to generate ML-DSA assertions" >&2
  return 1
}

write_ext_file() {
  local file="$1"
  local common_name="$2"
  shift 2

  {
    echo "[req]"
    echo "distinguished_name=req_distinguished_name"
    echo "req_extensions=v3_req"
    echo "prompt=no"
    echo "[req_distinguished_name]"
    echo "CN=$common_name"
    echo "[v3_req]"
    echo "keyUsage=critical,digitalSignature,keyEncipherment"
    echo "extendedKeyUsage=serverAuth"
    echo "subjectAltName=@alt_names"
    echo "[alt_names]"
    local index=1
    for dns_name in "$@"; do
      echo "DNS.$index=$dns_name"
      index=$((index + 1))
    done
  } > "$file"
}

write_client_ext_file() {
  local file="$1"
  local common_name="$2"

  {
    echo "[req]"
    echo "distinguished_name=req_distinguished_name"
    echo "req_extensions=v3_req"
    echo "prompt=no"
    echo "[req_distinguished_name]"
    echo "CN=$common_name"
    echo "[v3_req]"
    echo "keyUsage=critical,digitalSignature"
    echo "extendedKeyUsage=clientAuth"
  } > "$file"
}

issue_cert() {
  local name="$1"
  local common_name="$2"
  local out_dir="$3"
  shift 3
  local key_file="$out_dir/$name.key"
  local csr_file="$out_dir/$name.csr"
  local cert_file="$out_dir/$name.crt"
  local ext_file="$out_dir/$name.ext"

  mkdir -p "$out_dir"
  write_ext_file "$ext_file" "$common_name" "$@"
  openssl genrsa -out "$key_file" 2048 >/dev/null 2>&1
  openssl req -new -key "$key_file" -out "$csr_file" -config "$ext_file" >/dev/null 2>&1
  openssl x509 -req \
    -in "$csr_file" \
    -CA "$CA_CERT" \
    -CAkey "$CA_KEY" \
    -CAcreateserial \
    -out "$cert_file" \
    -days "$CERT_DAYS" \
    -sha256 \
    -extensions v3_req \
    -extfile "$ext_file" >/dev/null 2>&1
  rm -f "$csr_file" "$ext_file"
}

issue_client_cert() {
  local name="$1"
  local common_name="$2"
  local out_dir="$3"
  local key_file="$out_dir/$name.key"
  local csr_file="$out_dir/$name.csr"
  local cert_file="$out_dir/$name.crt"
  local ext_file="$out_dir/$name.ext"

  mkdir -p "$out_dir"
  write_client_ext_file "$ext_file" "$common_name"
  openssl genrsa -out "$key_file" 2048 >/dev/null 2>&1
  openssl req -new -key "$key_file" -out "$csr_file" -config "$ext_file" >/dev/null 2>&1
  openssl x509 -req \
    -in "$csr_file" \
    -CA "$CA_CERT" \
    -CAkey "$CA_KEY" \
    -CAcreateserial \
    -out "$cert_file" \
    -days "$CERT_DAYS" \
    -sha256 \
    -extensions v3_req \
    -extfile "$ext_file" >/dev/null 2>&1
  rm -f "$csr_file" "$ext_file"
}

echo "Generating lab internal CA..."
openssl genrsa -out "$CA_KEY" 4096 >/dev/null 2>&1
openssl req -x509 -new -nodes \
  -key "$CA_KEY" \
  -sha256 \
  -days "$CERT_DAYS" \
  -out "$CA_CERT" \
  -subj "/CN=saas-platform-internal-ca" \
  -addext "basicConstraints=critical,CA:TRUE,pathlen:1" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -addext "subjectKeyIdentifier=hash" >/dev/null 2>&1

echo "Generating Kong external TLS certificate..."
issue_cert kong localhost "$CA_DIR" localhost host.docker.internal

echo "Generating Kong upstream client certificate for mTLS..."
issue_client_cert kong-upstream-client kong-upstream-client "$CA_DIR"

echo "Generating Kong ML-DSA upstream client assertion..."
detect_python
"$PYTHON_BIN" - "$KONG_MLDSA_PRIVATE" "$KONG_MLDSA_PUBLIC" "$KONG_MLDSA_TOKEN" <<'PY'
from __future__ import annotations

import sys

from shared.pqc_signing import MLDSAKeyPair, MLDSASigner
from shared.s2s_token import create_s2s_token

private_path, public_path, token_path = sys.argv[1:]
keypair = MLDSAKeyPair.generate()
signer = MLDSASigner.from_keypair(keypair)
token = create_s2s_token(
    signer=signer,
    issuer="kong-gateway",
    subject="kong-upstream-client",
    audience="internal-upstream",
    tenant_id="platform",
    ttl_seconds=315360000,
    extra_claims={"purpose": "mldsa-authenticated-mtls"},
)

with open(private_path, "w", encoding="ascii", newline="\n") as file:
    file.write(keypair.private_key + "\n")
with open(public_path, "w", encoding="ascii", newline="\n") as file:
    file.write(keypair.public_key + "\n")
with open(token_path, "w", encoding="ascii", newline="\n") as file:
    file.write(token + "\n")
PY

declare -A SERVICES=(
  ["user-service"]="services/user-service/certs"
  ["resource-service"]="services/resource-service/certs"
  ["admin-service"]="services/admin-service/certs"
  ["payment-service"]="services/payment-service/certs"
)

for service in "${!SERVICES[@]}"; do
  echo "Generating upstream certificate for $service..."
  out_dir="${SERVICES[$service]}"
  issue_cert service "$service.svc.local" "$out_dir" "$service" "$service.svc.local"
  cp "$CA_CERT" "$out_dir/ca.crt"
  cp "$KONG_UPSTREAM_CLIENT_CERT" "$out_dir/health-client.crt"
  cp "$KONG_UPSTREAM_CLIENT_KEY" "$out_dir/health-client.key"
  cp "$KONG_MLDSA_PUBLIC" "$out_dir/mldsa-upstream-client.pub"
done

echo "Generated lab certificates under gateway/certs and services/*/certs."
echo "These files are intentionally ignored by Git."
