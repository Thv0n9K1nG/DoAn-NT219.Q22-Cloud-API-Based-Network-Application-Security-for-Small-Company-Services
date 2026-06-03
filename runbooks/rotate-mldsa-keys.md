# Runbook: Rotate ML-DSA Signing Keys

## When to use

Use this when an ML-DSA private key may be exposed, when scheduled key rotation is due, or before a final demo if the lab key material has been reused too much.

## Current implementation status

The current code supports one active key per purpose:

- `secret/pqc/s2s-signing`
- `secret/pqc/webhook-signing`

It does not yet support multiple `kid` values or old+new verifier sets. Therefore true zero-downtime rotation requires a small code change before production. For the course demo, a controlled rotation with short downtime is acceptable if documented.

## Controlled lab rotation

1. Start Vault:

```bash
docker compose up -d vault
bash scripts/vault-init.sh
```

2. Generate new keys into temporary paths:

```bash
python scripts/generate_mldsa_keys.py \
  --vault-addr http://localhost:8200 \
  --vault-token "$VAULT_DEV_TOKEN" \
  --key-path pqc/s2s-signing-next \
  --key-path pqc/webhook-signing-next
```

3. Stop services that sign or verify ML-DSA data:

```bash
docker compose stop user-service resource-service admin-service payment-service kong
```

4. Promote the new keys in Vault:

```bash
docker compose exec -T vault sh -lc '
  export VAULT_ADDR=http://127.0.0.1:8200
  export VAULT_TOKEN="${VAULT_DEV_TOKEN:-root-token-for-lab-only}"
  vault kv get -format=json secret/pqc/s2s-signing-next | jq -r ".data.data" > /tmp/s2s.json
  vault kv get -format=json secret/pqc/webhook-signing-next | jq -r ".data.data" > /tmp/webhook.json
  vault kv put secret/pqc/s2s-signing @/tmp/s2s.json
  vault kv put secret/pqc/webhook-signing @/tmp/webhook.json
'
```

If `jq` is not available in the Vault container, run `python scripts/generate_mldsa_keys.py` directly against the active paths instead.

5. Restart services:

```bash
docker compose up -d user-service resource-service admin-service payment-service kong
python -m pytest tests/test_pqc_signing.py tests/test_s2s_token.py tests/test_webhook_signer.py -q
```

## Production-grade rotation path

Before claiming zero-downtime rotation, implement:

1. Add `kid` to S2S token headers and outbound webhook headers.
2. Store key versions in Vault, for example `secret/pqc/s2s-signing/v1` and `v2`.
3. Make verifiers accept old and new public keys during the overlap window.
4. Switch signers to new `kid`.
5. Wait for max token TTL plus webhook replay window.
6. Remove old key from verifier set.
7. Archive or destroy old private key according to incident policy.

## Evidence to capture

- Output of key generation.
- Successful ML-DSA sign/verify benchmark after rotation.
- Tampered token/webhook still fails verification.
- Timestamp of old key retirement.
