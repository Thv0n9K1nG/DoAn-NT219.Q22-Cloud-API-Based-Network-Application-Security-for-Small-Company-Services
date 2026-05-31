# Stage 14 Observability: Loki, Promtail, Grafana Dashboards, and Alerts

Stage 14 adds the log-based observability plane for the lab. Promtail discovers
Docker containers, parses JSON service logs, and ships them to Loki. Grafana
provisions a Loki datasource, three dashboards, and four security alert rules.

## Scope Implemented

- Added request completion logs from shared request middleware with `event`,
  `method`, `path`, `status_code`, and `latency_ms`.
- Added `security.auth_failed` logs for API authentication failures.
- Standardized Stripe webhook signature failures as
  `security.invalid_webhook_signature`.
- Configured Promtail Docker service discovery through the Docker socket.
- Added JSON pipeline parsing for service log fields:

```text
timestamp
level
service
message
request_id
tenant_id
user_id
method
path
status_code
latency_ms
event
```

- Provisioned Grafana Loki datasource with stable UID `loki`.
- Added dashboards:
  - `api-traffic.json`
  - `security-events.json`
  - `tenant-activity.json`
- Added Grafana alert rules:
  - `HighAuthFailureRate`
  - `BOLAAttemptDetected`
  - `RateLimitViolation`
  - `StripeWebhookFailure`
- Bound Grafana and Loki host ports to `127.0.0.1` for local lab access only.

## Operational Model

Promtail reads Docker JSON logs from:

```text
/var/run/docker.sock
```

This is mounted read-only into the Promtail container. Docker metadata labels are
used to label log streams by Compose service name, project, container, and
stream. Service JSON log fields are parsed and selected fields become Loki
labels for dashboard and alert queries.

Grafana is available on:

```text
http://127.0.0.1:3000
```

Loki is available on:

```text
http://127.0.0.1:3100
```

The default lab Grafana credential is:

```text
admin / changeme-grafana
```

If you changed `GRAFANA_ADMIN_PASSWORD` in `.env`, use that value instead.

## Security Notes

- Promtail does not need application secrets. It only reads container logs.
- Observability files do not embed tokens, Stripe keys, Vault tokens, private
  keys, or generated gateway certificates.
- Structured logging redacts common secret field names such as `token`,
  `password`, `secret`, and `api_key`.
- Do not log raw JWTs or `Authorization` headers. Use request IDs, tenant IDs,
  user IDs, and JWT `jti` where needed.
- `gateway/kong.yml` remains generated/ignored and must not be committed because
  it can include internal certificate material.

## Test Commands

Run the observability config tests and related logging/webhook regressions:

```bash
pytest tests/test_observability_config.py services/resource-service/tests/test_logging.py services/payment-service/tests/test_stripe_webhook.py -v
```

Expected output:

```text
9 passed
```

Run Python bytecode validation:

```bash
python -m compileall shared services tests
```

Expected output:

```text
compileall exits 0
```

Validate Compose:

```bash
docker compose config --quiet
```

Expected output:

```text
no output and exit code 0
```

Start or recreate the observability stack:

```bash
docker compose up -d --force-recreate loki grafana promtail
```

Expected output includes:

```text
Container nt219-cloud-api-security-loki-1     Healthy
Container nt219-cloud-api-security-grafana-1  Healthy
Container nt219-cloud-api-security-promtail-1 Started
```

Check container ports and health:

```bash
docker compose ps loki grafana promtail
curl.exe -s http://127.0.0.1:3100/ready
curl.exe -s -u admin:changeme-grafana http://127.0.0.1:3000/api/health
```

Expected output includes:

```text
127.0.0.1:3100->3100/tcp
127.0.0.1:3000->3000/tcp
ready
"database":"ok"
```

Verify Grafana provisioning:

```bash
curl.exe -s -u admin:changeme-grafana http://127.0.0.1:3000/api/datasources/uid/loki
curl.exe -s -u admin:changeme-grafana "http://127.0.0.1:3000/api/search?query=NT219"
curl.exe -s -u admin:changeme-grafana http://127.0.0.1:3000/api/v1/provisioning/alert-rules
```

Expected datasource output includes:

```text
"uid":"loki"
"url":"http://loki:3100"
```

Expected dashboard output includes:

```text
NT219 API Traffic Overview
NT219 Security Events
NT219 Tenant Activity
```

Expected alert output includes:

```text
HighAuthFailureRate
BOLAAttemptDetected
RateLimitViolation
StripeWebhookFailure
```

Verify Loki labels populated by Promtail:

```bash
curl.exe -G -s "http://127.0.0.1:3100/loki/api/v1/labels"
```

Expected output includes:

```text
event
level
service
tenant_id
```

Promtail can warn that old container logs are too old for Loki ingestion after a
restart. That warning is acceptable when the service still discovers containers
and new logs are ingested.

## Manual Security Event Demo

Start the stack needed for gateway traffic:

```bash
bash scripts/kong-init.sh
docker compose up -d postgres redis vault keycloak opa user-service resource-service admin-service payment-service kong loki grafana promtail
```

Generate an invalid Stripe signature event:

```bash
curl.exe -k -i https://localhost:8443/webhooks/stripe ^
  -H "Content-Type: application/json" ^
  -H "Stripe-Signature: t=123,v1=forged" ^
  -d "{\"id\":\"evt_forged\",\"type\":\"payment_intent.succeeded\",\"data\":{\"object\":{\"id\":\"pi_forged\"}}}"
```

Expected output:

```text
HTTP/1.1 400 Bad Request
```

Query Loki for the event:

```bash
curl.exe -G -s "http://127.0.0.1:3100/loki/api/v1/query" --data-urlencode "query={event=\"security.invalid_webhook_signature\"}"
```

Expected output includes:

```text
"status":"success"
security.invalid_webhook_signature
```

Generate a BOLA event using the Stage 8 demo flow or later attack simulation,
then query Loki:

```bash
curl.exe -G -s "http://127.0.0.1:3100/loki/api/v1/query" --data-urlencode "query={event=\"security.bola_attempt\"}"
```

Expected output includes a `security.bola_attempt` log entry within roughly two
minutes of the attack simulation.

## Files Added or Changed

- `.env.example`
- `docker-compose.yml`
- `observability/promtail/config.yml`
- `observability/grafana/datasources/loki.yml`
- `observability/grafana/dashboards/dashboard-provider.yml`
- `observability/grafana/dashboards/api-traffic.json`
- `observability/grafana/dashboards/security-events.json`
- `observability/grafana/dashboards/tenant-activity.json`
- `observability/grafana/alerts/security-alerts.yaml`
- `shared/request_context.py`
- `shared/errors.py`
- `services/payment-service/app/api/v1/webhook.py`
- `tests/test_observability_config.py`

## Completion Criteria

Stage 14 is complete when:

- Loki, Grafana, and Promtail start successfully.
- Grafana provisions the Loki datasource, dashboards, and alert rules.
- Loki receives Docker logs through Promtail.
- Security events can be queried by `event` label.
- Tests pass and observability configuration files do not embed secrets.
