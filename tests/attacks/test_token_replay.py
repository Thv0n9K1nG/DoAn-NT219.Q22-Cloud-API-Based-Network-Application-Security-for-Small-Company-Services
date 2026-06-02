from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from shared.config import Settings
from shared.errors import register_error_handlers
from shared.pqc_signing import MLDSAKeyPair, MLDSASigner
from shared.s2s_token import S2STokenError, create_s2s_token, verify_s2s_token
from shared.security_middleware import CurrentUser, get_current_user


class StaticJWKSCache:
    """Small JWKS stand-in for deterministic Keycloak token attack tests."""

    def __init__(self, key):
        self.public_key = key.public_key()

    async def get_key(self, kid: str):
        if kid != "test-kid":
            raise AssertionError(f"unexpected kid: {kid}")
        return self.public_key


@pytest.fixture()
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture()
def client(signing_key):
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
        return {"user_id": user.user_id, "tenant_id": user.tenant_id, "jti": user.jti}

    return TestClient(app)


def test_expired_jwt_returns_401(client, signing_key):
    token = _make_token(signing_key, expires_delta=timedelta(minutes=-1))

    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def test_forged_jwt_signature_returns_401(client):
    attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = _make_token(attacker_key, expires_delta=timedelta(minutes=15))

    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def test_tampered_jwt_payload_returns_401(client, signing_key):
    token = _make_token(signing_key, expires_delta=timedelta(minutes=15))
    header, payload, signature = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims["tenant_id"] = "22222222-2222-2222-2222-222222222222"
    tampered_payload = base64.urlsafe_b64encode(
        json.dumps(claims, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")

    response = client.get("/me", headers={"Authorization": f"Bearer {header}.{tampered_payload}.{signature}"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def test_tampered_mldsa_s2s_token_fails_verification():
    signer = MLDSASigner.from_keypair(MLDSAKeyPair.generate())
    token = create_s2s_token(
        signer=signer,
        issuer="user-service",
        subject="user-service",
        audience="resource-service",
        tenant_id="11111111-1111-1111-1111-111111111111",
        now=1000,
        jti="stage16-s2s-jti",
    )
    header, payload, signature = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims["tenant_id"] = "22222222-2222-2222-2222-222222222222"
    tampered_payload = base64.urlsafe_b64encode(
        json.dumps(claims, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")

    with pytest.raises(S2STokenError, match="signature"):
        verify_s2s_token(
            f"{header}.{tampered_payload}.{signature}",
            signer=signer,
            expected_audience="resource-service",
            allowed_issuers=["user-service"],
            now=1001,
        )


def _make_token(signing_key, *, expires_delta: timedelta) -> str:
    now = datetime.now(UTC)
    claims = {
        "iss": "http://keycloak.test/realms/saas-platform",
        "aud": "saas-api",
        "sub": "kc-alpha-user",
        "email": "alpha-user@example.com",
        "tenant_id": "11111111-1111-1111-1111-111111111111",
        "org_name": "tenant-alpha",
        "realm_access": {"roles": ["tenant_user"]},
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": str(uuid4()),
    }
    return jwt.encode(claims, signing_key, algorithm="RS256", headers={"kid": "test-kid"})
