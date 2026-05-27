# Stage 4 Keycloak Setup

Stage 4 configures Keycloak as the OIDC identity provider for the SaaS lab.
The project uses one realm, `saas-platform`, and simulates tenant organizations
with user attributes:

| Tenant | `tenant_id`                            | `org_name`     |
| ------ | -------------------------------------- | -------------- |
| Alpha  | `11111111-1111-1111-1111-111111111111` | `tenant-alpha` |
| Beta   | `22222222-2222-2222-2222-222222222222` | `tenant-beta`  |

## Runtime

Keycloak uses PostgreSQL through Docker Compose. In this lab stage, port `18080`
is exposed on localhost so token and JWKS checks are easy to run from the host.
Do not expose this port directly in production.

## Rebuild / Init

```powershell
docker compose up -d postgres keycloak
bash scripts/keycloak-init.sh
```

## Token Check

```powershell
$TOKEN = bash scripts/get-token.sh alpha-user@example.com 'TestPass123!'
$env:TOKEN = $TOKEN
python -c "import base64,json,os; p=os.environ['TOKEN'].split('.')[1]; p += '='*((4-len(p)%4)%4); print(json.dumps(json.loads(base64.urlsafe_b64decode(p)), indent=2))"
```

Expected claims include:

- `tenant_id`
- `org_name`
- `realm_access.roles`
- `aud` containing `saas-api`
- `exp`
- `jti`

## JWKS Check

```powershell
curl http://localhost:18080/realms/saas-platform/protocol/openid-connect/certs
```

## Automated Check

```powershell
python scripts/test-keycloak-claims.py
```

## Import Artifact

`idp/realm-export.json` is mounted into the Keycloak container and imported on
fresh database startup through `start-dev --import-realm`. The init script is
still kept because it can upsert the same realm settings on an already running
lab database.
