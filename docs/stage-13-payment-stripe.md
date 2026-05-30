# Stage 13 Payment Service and Stripe Webhook Security

Stage 13 turns Payment Service from a skeleton into a Stripe-aware tenant payment
API. It creates tenant-scoped Payment Intents, verifies inbound Stripe webhooks
with Stripe HMAC, updates local payment state idempotently, and logs outbound
payment notifications signed with ML-DSA when payments succeed.

## Scope Implemented

- Added `POST /api/v1/payments/intent` for tenant users/admins.
- Added `GET /api/v1/payments` for tenant admins.
- Added `GET /api/v1/payments/{payment_id}` for same-tenant users/admins.
- Added root-level `POST /webhooks/stripe` without JWT dependency, matching the
  Kong bypass route from Stage 10.
- Added `PaymentService` orchestration around Stripe Payment Intent creation,
  Stripe webhook verification, local payment persistence, webhook idempotency,
  and outbound ML-DSA notification signing.
- Added `stripe_webhook_events` table in `scripts/db-init.sql` to record processed
  Stripe event IDs.
- Added tests for tenant-derived metadata, unsupported currency rejection,
  cross-tenant payment read denial, forged webhook rejection, valid webhook
  acceptance, and direct Stripe SDK verifier coverage.
- Added `stripe>=10,<19` to Payment Service and dev requirements.

## Security Behavior

Payment intent creation never accepts `tenant_id` from the client body. Tenant
and user identity come from the verified JWT claims:

```text
metadata = {
  "tenant_id": current_user.tenant_id,
  "user_id": current_user.user_id
}
```

Stripe inbound webhook verification uses:

```text
raw request body + Stripe-Signature header + secret/stripe/webhook_secret
```

This follows Stripe's official guidance to verify the exact raw body with the
endpoint secret. Forged signatures return `400 Bad Request`.

Outbound payment notifications are not sent to a real Notification Service yet.
For the lab, successful payment webhooks log a signed notification with:

```text
X-Webhook-Timestamp
X-Webhook-Signature: mldsa65=<signature>
X-Webhook-Algorithm: ML-DSA-65
```

This keeps the Stage 12 ML-DSA demo connected to the payment workflow without
pretending that Stripe inbound webhooks are post-quantum.

## Test Commands

Install/update dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

Run Payment Service tests:

```bash
pytest services/payment-service/tests -v
```

Expected output:

```text
services/payment-service/tests/test_health.py::test_live_health PASSED
services/payment-service/tests/test_openapi.py::test_openapi_schema PASSED
services/payment-service/tests/test_payments.py::test_create_payment_intent_uses_tenant_from_jwt PASSED
services/payment-service/tests/test_payments.py::test_create_payment_intent_rejects_unsupported_currency PASSED
services/payment-service/tests/test_payments.py::test_tenant_admin_lists_only_own_tenant_payments PASSED
services/payment-service/tests/test_payments.py::test_cross_tenant_payment_read_is_denied_and_logged PASSED
services/payment-service/tests/test_stripe_webhook.py::test_stripe_webhook_rejects_forged_signature PASSED
services/payment-service/tests/test_stripe_webhook.py::test_stripe_webhook_accepts_valid_signature_and_processes_event PASSED
services/payment-service/tests/test_stripe_webhook.py::test_payment_service_verifier_uses_stripe_sdk_construct_event PASSED
```

Run full Python regression:

```bash
pytest -v
```

Expected output:

```text
all tests pass
```

Validate Compose and build Payment Service:

```bash
docker compose config --quiet
docker compose build payment-service
```

Expected output:

```text
docker compose config --quiet exits 0
payment-service image builds successfully
```

Apply the updated schema to `paymentdb`:

```powershell
docker compose up -d postgres
cmd /c "type scripts\db-init.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d paymentdb"
cmd /c "type scripts\seed-data.sql | docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d paymentdb"
```

Expected output:

```text
COMMIT
```

Verify the webhook idempotency table exists:

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

## Manual Demo Commands

Initialize Vault secrets and ML-DSA keys:

```bash
docker compose up -d vault
bash scripts/vault-init.sh
python scripts/generate_mldsa_keys.py --vault-addr http://localhost:8200 --vault-token root-token-for-lab-only
```

Use a real Stripe sandbox key by setting `STRIPE_SECRET_KEY` and
`STRIPE_WEBHOOK_SECRET` before `scripts/vault-init.sh`, or write those values to
Vault manually. Do not commit real keys.

Create a Payment Intent through Kong:

```bash
TOKEN=$(./scripts/get-token.sh alpha-user@example.com TestPass123!)
curl -k -X POST https://localhost:8443/api/v1/payments/intent \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount": 2000, "currency": "usd"}'
```

Expected response shape:

```json
{
  "payment_id": "<uuid>",
  "payment_intent_id": "pi_...",
  "client_secret": "...",
  "status": "requires_payment_method"
}
```

Forged Stripe webhook through Kong:

```bash
curl -k -i https://localhost:8443/webhooks/stripe \
  -H "Content-Type: application/json" \
  -H "Stripe-Signature: t=123,v1=forged" \
  -d '{"id":"evt_forged","type":"payment_intent.succeeded","data":{"object":{"id":"pi_forged"}}}'
```

Expected status:

```text
HTTP/1.1 400 Bad Request
```

Stripe CLI local forwarding:

```bash
stripe listen --forward-to https://localhost:8443/webhooks/stripe
stripe trigger payment_intent.succeeded
```

If self-signed Kong TLS blocks local Stripe CLI forwarding, use a direct local
Payment Service route only for development.

## Operational Notes

- `gateway/kong.yml` is generated and ignored because it can embed internal CA
  material. Keep using `gateway/kong.template.yml` as the tracked source.
- Real Stripe keys belong in Vault, not Git. `.env.example` intentionally keeps
  only placeholders.
- The lab fallback `sk_test_lab_placeholder` creates local fake Payment Intent
  IDs so unit tests and demos can run without calling Stripe. Real Stripe sandbox
  behavior requires a real `sk_test...` key in Vault.

## References

- Stripe documentation: https://docs.stripe.com/webhooks?lang=python
- Stripe documentation: https://docs.stripe.com/webhooks/signature
