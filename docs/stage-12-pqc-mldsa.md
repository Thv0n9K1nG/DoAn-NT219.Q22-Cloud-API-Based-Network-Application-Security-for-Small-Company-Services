# Stage 12 PQC ML-DSA Application Signing

Stage 12 implements real ML-DSA-65 at the application layer for service-to-service
tokens and outbound webhook signatures. TLS remains classical, and Stripe
inbound webhook verification remains Stripe HMAC.

## Scope Implemented

- Added `shared/pqc_signing.py` with an `MLDSASigner` that loads base64-encoded
  ML-DSA-65 keys from Vault KV v2.
- Added `scripts/generate_mldsa_keys.py` to generate fresh ML-DSA-65 keypairs
  for `secret/pqc/s2s-signing` and `secret/pqc/webhook-signing`.
- Added `shared/s2s_token.py` for JWT-like S2S tokens:
  `base64url(header).base64url(payload).base64url(signature)`.
- Added `shared/webhook_signer.py` for canonical JSON outbound webhook signing.
- Added unit tests for key loading, tamper detection, token validation, replay
  checks, and invalid signatures.
- Added `tests/benchmarks/benchmark_mldsa.py` to capture latency and key/signature
  sizes for the final evaluation section.
- Updated service requirements to include `pqcrypto>=0.4,<0.5`.
- Updated Vault bootstrap so it no longer stores placeholder PQC private keys.

## Vault Key Generation

Start Vault and initialize the shared engines/policies:

```bash
docker compose up -d vault
bash scripts/vault-init.sh
```

Generate real ML-DSA-65 keys:

```bash
python scripts/generate_mldsa_keys.py --vault-addr http://localhost:8200 --vault-token root-token-for-lab-only
```

Expected output:

```text
stored secret/pqc/s2s-signing algorithm=ML-DSA-65 public_key_bytes=1952 private_key_bytes=4032 signature_bytes=3309
stored secret/pqc/webhook-signing algorithm=ML-DSA-65 public_key_bytes=1952 private_key_bytes=4032 signature_bytes=3309
ML-DSA private keys were written to Vault only and were not printed.
```

Verify the algorithm field without printing private key material:

```bash
docker compose exec -T -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN=root-token-for-lab-only vault vault kv get -field=algorithm secret/pqc/s2s-signing
docker compose exec -T -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN=root-token-for-lab-only vault vault kv get -field=algorithm secret/pqc/webhook-signing
```

Expected output for each command:

```text
ML-DSA-65
```

## S2S Token Format

The S2S token is JWT-like but is not a JWS library token. It uses:

- Header: `{"alg":"ML-DSA-65","typ":"JWT"}`
- Payload claims: `iss`, `sub`, `aud`, `iat`, `exp`, `jti`, `tenant_id`
- Signature input: `base64url(header).base64url(payload)`
- Signature: ML-DSA-65 signature encoded as base64url

Verification rejects:

- malformed token format,
- unsupported header,
- invalid or tampered signature,
- expired token,
- audience mismatch,
- issuer not in the allowlist,
- missing required claims.

## Outbound Webhook Signing

Outbound webhook signing uses canonical JSON:

```python
json.dumps(payload, sort_keys=True, separators=(",", ":"))
```

The signed bytes are:

```text
<timestamp>.<canonical-json>
```

Headers:

```text
X-Webhook-Timestamp: <unix timestamp>
X-Webhook-Signature: mldsa65=<base64 signature>
X-Webhook-Algorithm: ML-DSA-65
```

Verification rejects stale timestamps outside the default 300-second replay
window, missing or wrong algorithm headers, wrong signature prefix, tampered JSON,
and invalid base64 signatures.

## Test Commands

Install/update Python dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

Run the Stage 12 unit tests:

```bash
pytest tests/test_pqc_signing.py tests/test_s2s_token.py tests/test_webhook_signer.py -v
```

Expected output:

```text
tests/test_pqc_signing.py::test_mldsa_sign_and_verify_from_vault_secret PASSED
tests/test_pqc_signing.py::test_mldsa_rejects_missing_or_malformed_keys PASSED
tests/test_pqc_signing.py::test_mldsa_rejects_placeholder_or_wrong_size_keys PASSED
tests/test_pqc_signing.py::test_generated_key_sizes_match_mldsa65_constants PASSED
tests/test_s2s_token.py::test_s2s_token_round_trip_contains_required_claims PASSED
tests/test_s2s_token.py::test_s2s_token_rejects_expired_wrong_audience_or_issuer[...] PASSED
tests/test_s2s_token.py::test_s2s_token_rejects_tampered_payload PASSED
tests/test_s2s_token.py::test_s2s_token_rejects_malformed_token PASSED
tests/test_webhook_signer.py::test_webhook_signature_round_trip_with_canonical_json PASSED
tests/test_webhook_signer.py::test_webhook_signature_rejects_tampered_payload_and_signature_prefix PASSED
tests/test_webhook_signer.py::test_webhook_signature_rejects_replay_or_wrong_algorithm PASSED
```

Run the full Python test suite:

```bash
pytest -v
```

Expected output:

```text
all tests pass
```

Run the benchmark:

```bash
python tests/benchmarks/benchmark_mldsa.py --iterations 20
```

Expected output shape:

```text
ML-DSA-65 benchmark
iterations=20
message_size_bytes=256
keygen_ms=<machine-dependent>
sign_p50_ms=<machine-dependent>
sign_p95_ms=<machine-dependent>
verify_p50_ms=<machine-dependent>
verify_p95_ms=<machine-dependent>
signature_bytes=3309
public_key_bytes=1952
private_key_bytes=4032
```

## Notes for Collaborators

`scripts/vault-init.sh` deliberately avoids writing PQC placeholder private keys.
Run `scripts/generate_mldsa_keys.py` after Vault is ready. The script prints key
metadata only; it never prints private key bytes.

The S2S token implementation is intentionally separate from Keycloak JWT access
tokens. Keycloak remains responsible for user authentication. ML-DSA tokens are
for internal service assertions and application-layer authenticity demos.
