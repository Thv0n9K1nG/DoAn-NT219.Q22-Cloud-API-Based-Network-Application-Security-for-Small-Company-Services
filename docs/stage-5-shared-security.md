# Stage 5 Shared Security Library

Stage 5 adds shared FastAPI support code so later microservices do not duplicate
JWT verification, request context, structured logging, and error responses.

## Modules

| Module                          | Purpose                                                                        |
| ------------------------------- | ------------------------------------------------------------------------------ |
| `shared/config.py`              | Pydantic settings for Keycloak, JWT, Vault, database, and headers              |
| `shared/security_middleware.py` | RS256 JWT verification, JWKS cache, current user extraction, role dependencies |
| `shared/request_context.py`     | `contextvars` for request ID, tenant ID, and user ID                           |
| `shared/logging_config.py`      | JSON logging with request context and secret redaction                         |
| `shared/errors.py`              | Standard API error payloads and FastAPI exception handler registration         |

## Keycloak URLs

`KEYCLOAK_URL` is used to fetch JWKS. `JWT_ISSUER` is used to validate the
token `iss` claim. They can differ in the lab because users obtain tokens from
`localhost:18080`, while containers can reach Keycloak as `http://keycloak:8080`.

## Security Notes

- JWT signatures are verified with Keycloak JWKS and RS256.
- `aud`, `iss`, `exp`, `iat`, `jti`, and `sub` are enforced.
- `X-Tenant-ID` and `X-User-ID` are only correlation hints. The application user
  context is extracted from the verified JWT.
- Raw JWTs, passwords, client secrets, Stripe secrets, and API keys are redacted
  by the shared JSON formatter.

## Tests

```powershell
python -m pip install -r requirements-dev.txt
pytest services/resource-service/tests/test_security.py -v
pytest services/resource-service/tests/test_logging.py -v
```

Expected coverage:

- Missing bearer token returns `401`.
- Invalid and expired tokens return `401`.
- Valid alpha user token extracts the alpha tenant ID.
- Valid beta admin token includes `tenant_admin`.
- Tenant user is denied by `require_roles("tenant_admin")`.
- Logs are valid JSON and do not contain raw token or secret values.
