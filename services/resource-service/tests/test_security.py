from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from shared.config import Settings
from shared.errors import register_error_handlers
from shared.security_middleware import CurrentUser, get_current_user, require_roles


class StaticJWKSCache:
    def __init__(self, key):
        self.key = key.public_key()

    async def get_key(self, kid: str):
        if kid != "test-kid":
            raise AssertionError(f"unexpected kid: {kid}")
        return self.key


@pytest.fixture()
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture()
def app(signing_key):
    app = FastAPI()
    app.state.settings = Settings(
        SERVICE_NAME="resource-service",
        KEYCLOAK_URL="http://keycloak.test",
        KEYCLOAK_REALM="saas-platform",
        JWT_AUDIENCE="saas-api",
        JWT_ISSUER="http://keycloak.test/realms/saas-platform",
    )
    app.state.jwks_cache = StaticJWKSCache(signing_key)
    register_error_handlers(app)

    @app.get("/me")
    async def me(user: CurrentUser = Depends(get_current_user)):
        return {
            "user_id": user.user_id,
            "tenant_id": user.tenant_id,
            "email": user.email,
            "roles": user.roles,
            "jti": user.jti,
        }

    @app.get("/admin")
    async def admin(_: CurrentUser = Depends(require_roles("tenant_admin"))):
        return {"ok": True}

    return app


@pytest.fixture()
def client(app):
    return TestClient(app)


def make_token(signing_key, *, tenant_id: str, roles: list[str], expires_delta: timedelta):
    now = datetime.now(UTC)
    claims = {
        "iss": "http://keycloak.test/realms/saas-platform",
        "aud": "saas-api",
        "sub": "kc-user-id",
        "email": "user@example.com",
        "tenant_id": tenant_id,
        "org_name": "tenant-alpha",
        "realm_access": {"roles": roles},
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": str(uuid4()),
    }
    return jwt.encode(claims, signing_key, algorithm="RS256", headers={"kid": "test-kid"})


def test_missing_authorization_header_returns_401(client):
    response = client.get("/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_invalid_token_returns_401(client):
    response = client.get("/me", headers={"Authorization": "Bearer invalid.token.value"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def test_expired_token_returns_401(client, signing_key):
    token = make_token(
        signing_key,
        tenant_id="11111111-1111-1111-1111-111111111111",
        roles=["tenant_user"],
        expires_delta=timedelta(minutes=-1),
    )

    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def test_valid_alpha_user_extracts_tenant_context(client, signing_key):
    token = make_token(
        signing_key,
        tenant_id="11111111-1111-1111-1111-111111111111",
        roles=["tenant_user"],
        expires_delta=timedelta(minutes=15),
    )

    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "11111111-1111-1111-1111-111111111111"
    assert "tenant_user" in body["roles"]
    assert body["jti"]


def test_beta_admin_has_admin_role(client, signing_key):
    token = make_token(
        signing_key,
        tenant_id="22222222-2222-2222-2222-222222222222",
        roles=["tenant_admin", "read:resources"],
        expires_delta=timedelta(minutes=15),
    )

    response = client.get("/admin", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200


def test_require_roles_denies_tenant_user(client, signing_key):
    token = make_token(
        signing_key,
        tenant_id="11111111-1111-1111-1111-111111111111",
        roles=["tenant_user"],
        expires_delta=timedelta(minutes=15),
    )

    response = client.get("/admin", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCESS_DENIED"

