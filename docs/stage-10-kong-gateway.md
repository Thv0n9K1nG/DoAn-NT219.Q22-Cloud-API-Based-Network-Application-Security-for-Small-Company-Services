# Stage 10 Kong API Gateway

Stage 10 makes Kong the external API entry point for the lab. Kong runs in
DB-less mode so gateway routes, consumers, plugins, and upstreams are fully
reproducible from `gateway/kong.yml`.

## Scope Implemented

- Added Kong DB-less declarative config template in `gateway/kong.template.yml`.
- Added rendered Kong config in `gateway/kong.yml`.
- Added custom Kong plugin `opa-authz` under `gateway/plugins/opa-authz/`.
- Added `scripts/kong-init.sh` to render `gateway/kong.yml` from the current
  Keycloak realm public key.
- Added `scripts/kong-reset.sh` to re-render config and recreate Kong.
- Added `scripts/test-kong-gateway.sh` for gateway smoke tests.
- Added Kong service to `docker-compose.yml`.
- Added Kong/OPA lab ports to `.env.example`.

## Runtime Design

Kong is attached to:

- `dmz-net` for host access through `https://localhost:8443` and
  `http://localhost:8000`.
- `app-net` for upstream calls to FastAPI services, OPA, and Redis.

Routes:

| Public path         | Upstream service   | JWT | OPA | Notes                                          |
| ------------------- | ------------------ | --- | --- | ---------------------------------------------- |
| `/api/v1/users`     | `user-service`     | yes | yes | User tenant APIs                               |
| `/api/v1/resources` | `resource-service` | yes | yes | Includes Redis-backed rate limit               |
| `/api/v1/admin`     | `admin-service`    | yes | yes | Also has private-range IP restriction          |
| `/api/v1/payments`  | `payment-service`  | yes | yes | Payment API skeleton                           |
| `/webhooks/stripe`  | `payment-service`  | no  | no  | Inbound Stripe HMAC belongs in Payment Service |

Kong JWT validation uses Keycloak's realm public key. The JWT plugin verifies
the RS256 signature and expiration using the token `iss` claim as the Kong JWT
credential key. FastAPI services still verify JWTs again for defense-in-depth.

The `opa-authz` plugin runs after Kong JWT validation and before rate limiting.
It decodes verified JWT claims, injects `X-Tenant-ID`, `X-User-ID`, and
`X-Roles` for operational use, calls OPA `/v1/data/authz/allow`, and blocks the
request on deny.

## WAF-Lite Controls

Stage 10 intentionally does not claim full WAF coverage. Implemented controls:

- Request correlation ID with `X-Request-ID`.
- Strict CORS allowlist for local lab frontends.
- Request body size limit of 1 MB on API routes.
- JSON content-type enforcement for `POST`, `PUT`, and `PATCH` API requests in
  the `opa-authz` plugin.
- Private-range IP restriction on admin route.
- Redis-backed rate limiting on `/api/v1/resources`, keyed by injected
  `X-Tenant-ID`, with a lab quota of 20 requests/minute.

## Test Commands

Render Kong config from Keycloak and start the gateway stack:

```powershell
bash scripts/kong-init.sh
docker compose up -d postgres redis vault keycloak opa user-service resource-service admin-service payment-service kong
docker compose ps kong
```

Expected `docker compose ps kong` output:

```text
nt219-cloud-api-security-kong-1   kong:3.6.1   ...   Up ... (healthy)   0.0.0.0:8000->8000/tcp, 0.0.0.0:8443->8443/tcp
```

Run the full gateway smoke test:

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

Validate Kong config directly:

```powershell
docker run --rm `
  -v "${PWD}/gateway/kong.yml:/kong.yml:ro" `
  -v "${PWD}/gateway/plugins/opa-authz:/usr/local/share/lua/5.1/kong/plugins/opa-authz:ro" `
  -e KONG_DATABASE=off `
  -e KONG_DECLARATIVE_CONFIG=/kong.yml `
  -e KONG_PLUGINS=bundled,opa-authz `
  -e "KONG_LUA_PACKAGE_PATH=/usr/local/share/lua/5.1/?.lua;/usr/local/share/lua/5.1/?/init.lua;;" `
  kong:3.6.1 kong config parse /kong.yml
```

Expected output:

```text
parse successful
```

Manual no-token check:

```powershell
curl.exe -k -i https://localhost:8443/api/v1/resources
```

Expected status:

```text
HTTP/1.1 401 Unauthorized
X-Request-ID: <uuid>
```

Manual valid-token check:

```powershell
$TOKEN = bash scripts/get-token.sh alpha-user@example.com 'TestPass123!'
curl.exe -k -i https://localhost:8443/api/v1/resources -H "Authorization: Bearer $TOKEN"
```

Expected status:

```text
HTTP/1.1 200 OK
```

Manual OPA deny check:

```powershell
$TOKEN = bash scripts/get-token.sh alpha-user@example.com 'TestPass123!'
curl.exe -k -i https://localhost:8443/api/v1/admin/tenants -H "Authorization: Bearer $TOKEN"
```

Expected status:

```text
HTTP/1.1 403 Forbidden
{"error":{"code":"ACCESS_DENIED","message":"Access denied by authorization policy"}}
```

## Operational Notes

- Run `scripts/kong-init.sh` after resetting Keycloak because Keycloak realm
  signing keys can change.
- Run `scripts/kong-reset.sh` after changing gateway config or the custom plugin.
- TLS on `8443` uses Kong's lab/default certificate. External TLS hardening and
  mTLS to upstream services are Stage 11 work.1111111111111111111A
