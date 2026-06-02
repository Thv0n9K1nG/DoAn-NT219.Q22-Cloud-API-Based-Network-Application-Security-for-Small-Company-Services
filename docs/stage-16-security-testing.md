# Stage 16 Security Testing and Attack Simulation

Stage 16 adds a repeatable attack simulation suite for the core security
controls in this lab: BOLA prevention, token tampering rejection, rate limiting,
SSRF input blocking, Stripe webhook signature verification, OPA authorization
policy tests, and ZAP API scanning.

## Scope Implemented

- Added `tests/attacks/test_bola.py`.
  - Simulates Beta tenant reading an Alpha tenant resource through the Resource
    Service API.
  - Expected result: `403 Forbidden`.
  - Expected evidence: `security.bola_attempt` log with attacker tenant,
    resource tenant, user id, and resource id.
- Added `tests/attacks/test_token_replay.py`.
  - Covers expired JWT, forged JWT signature, tampered JWT payload, and tampered
    ML-DSA service-to-service token.
  - Expected result: HTTP token attacks return `401`; ML-DSA tampering raises a
    signature verification failure.
- Added `tests/attacks/test_rate_limiting.py`.
  - Uses a deterministic fixed-window model of the gateway quota.
  - Expected result: requests above the configured window return simulated
    `429`.
- Added `tests/attacks/test_ssrf.py`.
  - Tests Resource Service URL validation against metadata, localhost, internal
    service names, file scheme, and loopback payloads.
  - Expected result: validator rejects internal targets; API returns `422` for
    the SSRF request body.
- Added `tests/attacks/test_webhook_forgery.py`.
  - Sends a forged Stripe webhook signature and a valid signature control case
    through the Payment Service webhook API.
  - Expected result: forged request returns `400`; valid control request returns
    `200`.
- Added `tests/run_security_tests.sh`.
  - Runs OPA policy tests, unit regression tests, attack simulations, and the
    local ZAP OpenAPI scan.
  - Writes JUnit XML reports into `tests/reports/`, which stays ignored by Git.
- Hardened Resource Service URL DTOs.
  - `ResourceCreate.url` and `ResourceUpdate.url` now reject internal hosts and
    private, loopback, link-local, reserved, or unspecified IP addresses.

## Test Commands

Run only the attack simulation suite:

```bash
python -m pytest tests/attacks -v --tb=short
```

Expected output:

```text
tests/attacks/test_bola.py::test_cross_tenant_resource_read_returns_403_and_emits_bola_log PASSED
tests/attacks/test_rate_limiting.py::test_rate_limit_returns_429_after_configured_minute_quota PASSED
tests/attacks/test_rate_limiting.py::test_rate_limit_counter_is_isolated_by_identity PASSED
tests/attacks/test_ssrf.py::test_resource_url_validator_blocks_internal_targets[...] PASSED
tests/attacks/test_ssrf.py::test_create_resource_api_returns_422_for_internal_url PASSED
tests/attacks/test_token_replay.py::test_expired_jwt_returns_401 PASSED
tests/attacks/test_token_replay.py::test_forged_jwt_signature_returns_401 PASSED
tests/attacks/test_token_replay.py::test_tampered_jwt_payload_returns_401 PASSED
tests/attacks/test_token_replay.py::test_tampered_mldsa_s2s_token_fails_verification PASSED
tests/attacks/test_webhook_forgery.py::test_stripe_webhook_forged_signature_returns_400_and_skips_processing PASSED
18 passed
```

Run targeted regression around the changed service surfaces:

```bash
python -m pytest services/resource-service/tests/test_resource_routes.py services/resource-service/tests/test_openapi.py services/payment-service/tests/test_stripe_webhook.py tests/test_s2s_token.py tests/attacks -v --tb=short
```

Expected output:

```text
33 passed
```

Run the full Stage 16 security runner:

```bash
bash tests/run_security_tests.sh
```

Expected output:

```text
=== OPA Policy Tests ===
PASS: 14/14
=== Unit Regression Tests ===
58 passed
=== Attack Simulations ===
18 passed
=== ZAP API Scan ===
Total of 45 URLs
FAIL-NEW: 0
WARN-NEW: 2
PASS: 117
=== Security tests complete ===
```

The two ZAP warnings currently observed are the same local lab findings from
Stage 15:

```text
Strict-Transport-Security Header Not Set [10035]
Server Leaks Version Information via "Server" HTTP Response Header Field [10036]
```

Generated local evidence:

```text
tests/reports/security-unit-report.xml
tests/reports/security-attack-report.xml
tests/reports/zap-report.json
tests/reports/zap-report.html
tests/reports/zap-openapi.json
```

These files are intentionally ignored because reports may contain request paths,
headers, local topology, and other lab details.

## Result Matrix

| Test                      | Expected           | Actual                                  | Status             | Evidence                                |
| ------------------------- | ------------------ | --------------------------------------- | ------------------ | --------------------------------------- |
| BOLA                      | `403` and BOLA log | `403`, `security.bola_attempt` asserted | PASS               | `tests/attacks/test_bola.py`            |
| Expired JWT               | `401`              | `401 INVALID_TOKEN`                     | PASS               | `tests/attacks/test_token_replay.py`    |
| Forged JWT signature      | `401`              | `401 INVALID_TOKEN`                     | PASS               | `tests/attacks/test_token_replay.py`    |
| Tampered JWT payload      | `401`              | `401 INVALID_TOKEN`                     | PASS               | `tests/attacks/test_token_replay.py`    |
| Tampered ML-DSA S2S token | verify fail        | `S2STokenError: signature`              | PASS               | `tests/attacks/test_token_replay.py`    |
| Rate limiting             | `429` after quota  | first 20 allowed, next 5 blocked        | PASS               | `tests/attacks/test_rate_limiting.py`   |
| SSRF metadata host        | `400/422/403`      | validator rejects                       | PASS               | `tests/attacks/test_ssrf.py`            |
| SSRF localhost/IP         | `400/422/403`      | API returns `422`                       | PASS               | `tests/attacks/test_ssrf.py`            |
| Stripe webhook forgery    | `400`              | `400 BAD_REQUEST`                       | PASS               | `tests/attacks/test_webhook_forgery.py` |
| OPA policy regression     | all pass           | `PASS: 14/14`                           | PASS               | `bash scripts/test-opa.sh`              |
| Unit regression           | all pass           | `58 passed`                             | PASS               | `tests/run_security_tests.sh`           |
| ZAP API scan              | no new fail        | `FAIL-NEW: 0`, `WARN-NEW: 2`            | PASS with warnings | `tests/reports/zap-report.html`         |

## Manual Full-Stack Checks

Start the stack before running manual gateway checks:

```bash
docker compose up -d
```

BOLA and webhook demos can reuse the Stage 8 and Stage 13 commands. The
automated Stage 16 suite intentionally keeps the attack payloads inside the lab
and does not scan or attack any third-party target.

For ZAP, the runner delegates to `scripts/test-zap-local.ps1`, which generates a
temporary OpenAPI document with this target:

```text
https://host.docker.internal:8443
```

This avoids the earlier problem where the ZAP container could not fetch
`https://localhost:8443/openapi.json` from inside Docker.

## Limit

- Rate limiting is tested with a deterministic fixed-window model, not by
  exhausting Kong through the full gateway on every pytest run. This keeps the
  attack suite fast and stable, but it does not prove every Kong runtime log
  path in the same test.
- SSRF is tested as URL input validation. The current Resource Service stores
  URL metadata but does not fetch remote URLs, so there is no real outbound SSRF
  execution path to exercise yet.
- Refresh-token reuse is not automated. It needs a Keycloak browser/session or
  refresh-token flow with rotation settings enabled and stable test users.
- ZAP runs unauthenticated against OpenAPI routes. It proves baseline API
  exposure and common passive/active findings, but it does not crawl authenticated
  tenant workflows.
- Local ZAP still reports HSTS and `Server` response header warnings because the
  lab runs Kong with a self-signed local TLS setup and upstream default headers.

## To Do Next

- Add an authenticated ZAP context after the final demo users and token refresh
  workflow are frozen.
- Add an optional full-stack Kong rate-limit attack script that collects Loki
  evidence for `429` events and stores only sanitized summaries.
- If a future feature fetches user-supplied URLs, move SSRF coverage from schema
  validation into an egress-blocking integration test with mocked DNS and blocked
  metadata service targets.
- Enable Keycloak refresh-token rotation in the lab realm and add a replay test
  for reused refresh tokens.
- Decide whether to enforce HSTS and suppress upstream `Server` headers in Kong
  for the final hardening stage, then update the ZAP baseline accordingly.
