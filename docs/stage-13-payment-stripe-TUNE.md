# Stage 13 Manual Demo Tuning Notes

This note explains the failures observed during the Stage 13 manual demo and the
steps needed to make the gateway demo line up with the expected output.

## What Happened

### 1. `{"exp":"token expired"}`

This was a stale Keycloak access token. The first request reused an old
`$TOKEN`, so Kong rejected it before the request reached Payment Service.

Fix:

```powershell
$TOKEN = (bash scripts/get-token.sh alpha-user@example.com 'TestPass123!').Trim()
```

Then immediately retry the request. Access tokens in this lab are intentionally
short-lived.

### 2. `ACCESS_DENIED` on `POST /api/v1/payments/intent`

This was an OPA RBAC data mismatch.

Payment Service route code allows:

```text
tenant_user, tenant_admin
```

But the OPA role data still only allowed `write:billing` for `platform_admin`.
Kong asks OPA before forwarding to Payment Service, so OPA returned deny and
Kong correctly returned:

```json
{"error":{"code":"ACCESS_DENIED","message":"Access denied by authorization policy"}}
```

Fix applied:

- `tenant_user` now has `write:billing`.
- `tenant_admin` now has `write:billing`.
- OPA tests now cover `POST /api/v1/payments/intent`.

Validate:

```powershell
bash scripts/test-opa.sh
```

Expected output:

```text
PASS: 14/14
```

After changing OPA data, restart OPA because it loads policy/data at startup:

```powershell
docker compose up -d --force-recreate opa
```

### 3. Forged webhook returned `404 Not Found`

The response had `server: uvicorn` and `X-Kong-Upstream-Latency`, which means
Kong did route the request to `payment-service`. The `404` came from the upstream
Payment Service app, not from Kong.

That usually means the running Payment Service container is still using the old
Stage 7/8 image that does not include:

```text
POST /webhooks/stripe
```

Fix:

```powershell
docker compose build payment-service
docker compose up -d --force-recreate payment-service
```

Verify the route exists inside the running container:

```powershell
docker compose exec -T payment-service python -c "from app.main import app; print([r.path for r in app.routes if 'webhooks' in r.path or 'payments/intent' in r.path])"
```

Expected output includes:

```text
'/api/v1/payments/intent'
'/webhooks/stripe'
```

If Kong config was regenerated or `gateway/kong.yml` was deleted locally, render
it again and recreate Kong:

```powershell
bash scripts/kong-init.sh
docker compose up -d --force-recreate kong
```

`gateway/kong.yml` is generated and ignored because it can contain internal trust
material.

### 4. `stripe` command not found

The Stripe Python package used by Payment Service is not the Stripe CLI. The CLI
is a separate binary and must be installed before these commands work:

```powershell
stripe listen --forward-to https://localhost:8443/webhooks/stripe
stripe trigger payment_intent.succeeded
```

Install the Stripe CLI from the official Stripe docs:

```text
https://docs.stripe.com/stripe-cli/install
```

On Windows, Stripe documents install options such as Scoop or downloading the
Windows archive. After installation:

```powershell
stripe login
stripe --version
```

## Important Vault and `.env` Detail

Adding `STRIPE_SECRET_KEY` to `.env` is not enough unless the Vault bootstrap
script reads `.env` before writing secrets.

Fix applied:

```text
scripts/vault-init.sh now sources .env explicitly.
```

This matters because Docker Compose reads `.env` for Compose interpolation, but
running `bash scripts/vault-init.sh` from PowerShell does not automatically
export `.env` variables into that Bash process.

Recommended `.env` entries for the payment demo:

```env
STRIPE_SECRET_KEY=sk_test_your_real_sandbox_key
STRIPE_WEBHOOK_SECRET=whsec_your_cli_or_dashboard_endpoint_secret
PAYMENT_SVC_VAULT_ROLE_ID=<value printed by scripts/vault-init.sh>
PAYMENT_SVC_VAULT_SECRET_ID=<value printed by scripts/vault-init.sh>
```

If `STRIPE_WEBHOOK_SECRET` is only known after `stripe listen`, write it into
Vault directly:

```powershell
docker compose exec -T `
  -e VAULT_ADDR=http://127.0.0.1:8200 `
  -e VAULT_TOKEN=root-token-for-lab-only `
  vault vault kv put secret/stripe/webhook_secret value="whsec_from_stripe_listen"
```

Then recreate Payment Service so its Vault/AppRole environment is fresh:

```powershell
docker compose up -d --force-recreate payment-service
```

## Clean Manual Demo Sequence

Run this from a fresh PowerShell session after pulling/confirming Stage 13 code.

### 1. Prepare Vault secrets and ML-DSA keys

```powershell
docker compose up -d vault
bash scripts/vault-init.sh
python scripts/generate_mldsa_keys.py --vault-addr http://localhost:8200 --vault-token root-token-for-lab-only
```

Copy the printed `PAYMENT_SVC_VAULT_ROLE_ID` and
`PAYMENT_SVC_VAULT_SECRET_ID` into `.env`.

### 2. Rebuild/recreate the runtime that changed

```powershell
bash scripts/generate-dev-certs.sh
docker compose build payment-service
docker compose up -d postgres redis vault keycloak opa
docker compose up -d --force-recreate opa payment-service
```

### 3. Apply the payment database schema

```powershell
cmd /c "type scripts\db-init.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d paymentdb"
cmd /c "type scripts\seed-data.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d paymentdb"
```

Expected output includes:

```text
COMMIT
```

Verify idempotency table:

```powershell
docker compose exec -T postgres psql -U postgres -d paymentdb -c "\d stripe_webhook_events"
```

Expected output includes:

```text
event_id
event_type
payment_intent_id
processed_at
```

### 4. Re-render Kong config and recreate Kong

```powershell
bash scripts/keycloak-init.sh
bash scripts/kong-init.sh
docker compose up -d --force-recreate kong
```

### 5. Verify OPA allows payment intent

```powershell
$OPA_INPUT = New-TemporaryFile
@'
{"input":{"method":"POST","path":["api","v1","payments","intent"],"tenant_id":"11111111-1111-1111-1111-111111111111","user_id":"kc-alpha-user","roles":["tenant_user"]}}
'@ | Set-Content -NoNewline $OPA_INPUT

curl.exe -s -X POST http://localhost:8181/v1/data/authz/allow `
  -H "Content-Type: application/json" `
  --data-binary "@$OPA_INPUT"

Remove-Item $OPA_INPUT
```

Expected output:

```json
{"result":true}
```

### 6. Create a Payment Intent through Kong

```powershell
$TOKEN = (bash scripts/get-token.sh alpha-user@example.com 'TestPass123!').Trim()

curl.exe -k -X POST https://localhost:8443/api/v1/payments/intent `
  -H "Authorization: Bearer $TOKEN" `
  -H "Content-Type: application/json" `
  -d "{\`"amount\`": 2000, \`"currency\`": \`"usd\`"}"
```

Expected output shape with a real Stripe sandbox key:

```json
{
  "payment_id": "<uuid>",
  "payment_intent_id": "pi_...",
  "client_secret": "...",
  "status": "requires_payment_method"
}
```

If Payment Service cannot read the real Stripe key from Vault, it falls back to
the lab placeholder and returns a local fake ID:

```text
pi_lab_...
```

That means the app route works, but the Stripe secret path is not configured
correctly yet.

### 7. Verify forged webhook rejection

```powershell
curl.exe -k -i https://localhost:8443/webhooks/stripe `
  -H "Content-Type: application/json" `
  -H "Stripe-Signature: t=123,v1=forged" `
  -d '{"id":"evt_forged","type":"payment_intent.succeeded","data":{"object":{"id":"pi_forged"}}}'
```

Expected status:

```text
HTTP/1.1 400 Bad Request
```

If this returns `404` with `server: uvicorn`, rebuild and recreate
`payment-service`; the container is still running an old app image.

## Quick Diagnosis Table

| Symptom                                      | Most likely cause                                          | Fix                                                                                     |
| -------------------------------------------- | ---------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `{"exp":"token expired"}`                    | stale access token                                         | refresh `$TOKEN` with `scripts/get-token.sh`                                            |
| `ACCESS_DENIED`                              | OPA role data missing `write:billing` or OPA not restarted | apply role fix, run `bash scripts/test-opa.sh`, recreate `opa`                          |
| `/webhooks/stripe` returns upstream `404`    | old Payment Service container image                        | `docker compose build payment-service` then force recreate                              |
| `stripe` not recognized                      | Stripe CLI not installed                                   | install Stripe CLI from official Stripe docs                                            |
| response has `pi_lab_...`                    | Payment Service did not read real Stripe key from Vault    | ensure `.env` is sourced by `vault-init.sh`, rerun Vault init, recreate Payment Service |
| valid Stripe CLI webhook still returns `400` | wrong `STRIPE_WEBHOOK_SECRET` in Vault                     | copy `whsec_...` from `stripe listen` into Vault and recreate Payment Service           |
