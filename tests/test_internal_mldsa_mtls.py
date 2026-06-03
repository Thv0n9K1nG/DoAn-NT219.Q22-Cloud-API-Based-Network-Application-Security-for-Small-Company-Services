from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from shared.config import Settings
from shared.internal_mldsa_mtls import InternalMLDSAMTLSMiddleware
from shared.pqc_signing import MLDSAKeyPair, MLDSASigner
from shared.s2s_token import create_s2s_token


def make_app(public_key_file: str) -> FastAPI:
    app = FastAPI()
    settings = Settings(
        SERVICE_NAME="test-service",
        INTERNAL_MLDSA_MTLS_REQUIRED=True,
        INTERNAL_MLDSA_PUBLIC_KEY_FILE=public_key_file,
    )
    app.add_middleware(InternalMLDSAMTLSMiddleware, settings=settings)

    @app.get("/api/v1/protected")
    async def protected():
        return {"status": "ok"}

    @app.get("/health/live")
    async def live():
        return {"status": "live"}

    return app


def test_internal_mldsa_mtls_accepts_signed_kong_assertion(tmp_path):
    keypair = MLDSAKeyPair.generate()
    public_key_file = tmp_path / "mldsa-upstream-client.pub"
    public_key_file.write_text(keypair.public_key, encoding="ascii")
    token = create_s2s_token(
        signer=MLDSASigner.from_keypair(keypair),
        issuer="kong-gateway",
        subject="kong-upstream-client",
        audience="internal-upstream",
        tenant_id="platform",
    )

    client = TestClient(make_app(str(public_key_file)))

    response = client.get("/api/v1/protected", headers={"X-Internal-MLDSA-Token": token})

    assert response.status_code == 200


def test_internal_mldsa_mtls_rejects_missing_assertion_but_skips_health(tmp_path):
    keypair = MLDSAKeyPair.generate()
    public_key_file = tmp_path / "mldsa-upstream-client.pub"
    public_key_file.write_text(keypair.public_key, encoding="ascii")
    client = TestClient(make_app(str(public_key_file)))

    protected_response = client.get("/api/v1/protected")
    health_response = client.get("/health/live")

    assert protected_response.status_code == 401
    assert protected_response.json()["detail"] == "Missing ML-DSA upstream client assertion"
    assert health_response.status_code == 200
