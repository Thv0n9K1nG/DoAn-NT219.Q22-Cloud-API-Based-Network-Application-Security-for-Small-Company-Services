# Runbook: BOLA Incident Response

## Trigger

Use this when Grafana alert `BOLAAttemptDetected` fires or logs contain `event="security.bola_attempt"` / `event="security.payment_bola_attempt"`.

## Immediate triage

1. Open Grafana.
2. Go to the `NT219 Security Events` dashboard.
3. Query Loki:

```logql
{event="security.bola_attempt"}
```

For payment objects:

```logql
{event="security.payment_bola_attempt"}
```

4. Record:

- `request_id`
- `user_id`
- `attacker_tenant_id`
- `resource_id` or `payment_id`
- `resource_tenant_id` or `payment_tenant_id`
- source IP if present in Kong logs
- timestamp

## Containment

1. Revoke the suspected user's sessions:

```bash
bash runbooks/revoke-user-sessions.sh beta-user@example.com
```

2. If attack traffic continues, block the source IP at the firewall or add temporary Kong IP restriction rules.
3. Do not delete evidence logs until the incident report is written.

## Impact check

1. Confirm the response status was `403`.
2. Confirm no sensitive response body was returned.
3. Search for successful reads of the same object around the same time:

```logql
{event="resource.read", resource_id="<resource-id>"}
```

4. Check whether the attacker account has unexpected roles in Keycloak.

## Recovery validation

Run:

```bash
python -m pytest tests/attacks/test_bola.py -q
bash scripts/test-kong-gateway.sh
```

Expected result:

- Cross-tenant read returns `403`.
- `security.bola_attempt` is logged.
- Tenant-owned reads still work for the correct tenant.

## Report template

```text
Incident:
Detected at:
Detected by:
Attacker user_id:
Attacker tenant_id:
Target object:
Target tenant_id:
HTTP status returned:
Data exposure confirmed: yes/no
Containment actions:
Root cause:
Fixes applied:
Validation commands:
Residual risk:
```
