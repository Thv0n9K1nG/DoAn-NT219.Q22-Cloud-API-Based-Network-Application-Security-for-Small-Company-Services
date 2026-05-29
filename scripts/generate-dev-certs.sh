#!/bin/bash
set -euo pipefail

CERT_DAYS="${CERT_DAYS:-365}"
CA_DIR="gateway/certs"
CA_KEY="$CA_DIR/internal-ca.key"
CA_CERT="$CA_DIR/internal-ca.crt"
KONG_KEY="$CA_DIR/kong.key"
KONG_CERT="$CA_DIR/kong.crt"

mkdir -p "$CA_DIR"

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
done

echo "Generated lab certificates under gateway/certs and services/*/certs."
echo "These files are intentionally ignored by Git."
