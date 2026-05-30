# Stage 11 TLS Network Plane

Stage 11 adds real TLS to the local lab network plane. Clients call Kong over
HTTPS, and Kong routes to FastAPI upstream services over HTTPS with internal CA
verification.

## Scope Implemented

- Added `scripts/generate-dev-certs.sh` to generate a lab internal CA, Kong
  external TLS certificate, and per-service upstream certificates.
- Added `scripts/test-tls-plane.sh` to validate external TLS and Kong-to-service
  HTTPS upstream verification.
- Added `scripts/vault-issue-certs.sh` as a documented placeholder for future
  Vault PKI issuance.
- Added cert directories with `.gitkeep` files:
  - `gateway/certs/`
  - `services/user-service/certs/`
  - `services/resource-service/certs/`
  - `services/admin-service/certs/`
  - `services/payment-service/certs/`
- Updated Compose so each FastAPI service runs Uvicorn with `service.crt` and
  `service.key`.
- Updated Kong to use `gateway/certs/kong.crt` and `gateway/certs/kong.key` for
  external TLS.
- Updated Kong DB-less config to route upstreams via `https://...` with
  `tls_verify: true`, `tls_verify_depth: 2`, and an internal CA certificate
  entity.
- Updated `docs/limitations.md` with honest TLS/mTLS/PQC limitations.

## Implemented Trust Level

This stage implements:

- External TLS: client -> Kong over HTTPS.
- Upstream TLS with CA verification: Kong verifies FastAPI service certificates.

This stage does not claim full mTLS. The FastAPI services do not currently
require a Kong client certificate. Full mTLS would require Kong to present a
client certificate and each service to enforce client certificate validation.

## Certificate Generation

Generate all lab certificates:

```powershell
bash scripts/generate-dev-certs.sh
```

Expected output:

```text
Generating lab internal CA...
Generating Kong external TLS certificate...
Generating upstream certificate for payment-service...
Generating upstream certificate for resource-service...
Generating upstream certificate for admin-service...
Generating upstream certificate for user-service...
Generated lab certificates under gateway/certs and services/*/certs.
These files are intentionally ignored by Git.
```

The generated private keys, certificates, and rendered `gateway/kong.yml` are
ignored by Git. `gateway/kong.yml` is rendered from `gateway/kong.template.yml`
and can include internal trust material required by Kong DB-less mode.

## Test Commands

Run the Stage 11 TLS plane test:

```powershell
bash scripts/test-tls-plane.sh
```

Expected output:

```text
Preparing Stage 11 TLS plane test...
External Kong TLS certificate:
subject=CN = localhost
issuer=CN = saas-platform-internal-ca
Verifying resource-service upstream certificate from Kong container...
resource-service upstream certificate verify: ok
external TLS no-token gateway request      expected=401 actual=401
Kong routes to HTTPS upstream              expected=200 actual=200
Stage 11 TLS plane test passed.
```

Run the gateway regression test after TLS changes:

```powershell
bash scripts/test-kong-gateway.sh
```

Expected output:

```text
no token is rejected by gateway            expected=401 actual=401
tenant user can list resources             expected=200 actual=200
tenant user is denied admin route by OPA   expected=403 actual=403
non-json API write is rejected             expected=415 actual=415
stripe webhook route bypasses JWT          expected=not-401 actual=404
rate limit status summary:
     20 200
      5 429
Stage 10 Kong gateway smoke test passed.
```

Inspect Kong's external certificate manually:

```Bash
openssl s_client -connect localhost:8443 -servername localhost </dev/null 2>$null | openssl x509 -noout -subject -issuer
```

Powershell version:

```powershell
"" | openssl s_client -connect localhost:8443 -servername localhost 2>$null | openssl x509 -noout -subject -issuer
```

Expected output:

```text
subject=CN = localhost
issuer=CN = saas-platform-internal-ca
```

Verify an upstream certificate from inside Kong:

```powershell
docker compose exec -T kong sh -c "openssl s_client -connect resource-service:8000 -servername resource-service -CAfile /etc/kong/certs/internal-ca.crt -verify_return_error </dev/null 2>&1 | grep 'Verify return code'"
```

Expected output:

```text
Verify return code: 0 (ok)
```

Manual end-to-end request through HTTPS gateway and HTTPS upstream:

```powershell
$TOKEN = bash scripts/get-token.sh alpha-user@example.com 'TestPass123!'
curl.exe -k -i https://localhost:8443/api/v1/resources -H "Authorization: Bearer $TOKEN"
```

Expected status:

```text
HTTP/1.1 200 OK
```

## Operational Notes

- Run `bash scripts/generate-dev-certs.sh` before first Compose startup on a new
  machine.
- Recreate microservice containers after regenerating service certificates so
  Uvicorn reloads the new keypairs.
- Run `bash scripts/kong-init.sh` after regenerating certificates or resetting
  Keycloak so `gateway/kong.yml` contains the current public key and internal
  CA.
- Run `bash scripts/kong-reset.sh` after rendering a new Kong config.
