from __future__ import annotations

import base64
import json

import pytest

from shared.pqc_signing import MLDSAKeyPair, MLDSASigner
from shared.s2s_token import S2STokenError, create_s2s_token, verify_s2s_token


def _signer() -> MLDSASigner:
    return MLDSASigner.from_keypair(MLDSAKeyPair.generate())


def test_s2s_token_round_trip_contains_required_claims():
    signer = _signer()

    token = create_s2s_token(
        signer=signer,
        issuer="user-service",
        subject="user-service",
        audience="resource-service",
        tenant_id="tenant-alpha",
        now=1000,
        jti="jti-1",
    )

    claims = verify_s2s_token(
        token,
        signer=signer,
        expected_audience="resource-service",
        allowed_issuers=["user-service"],
        now=1001,
    )

    assert claims["iss"] == "user-service"
    assert claims["sub"] == "user-service"
    assert claims["aud"] == "resource-service"
    assert claims["tenant_id"] == "tenant-alpha"
    assert claims["jti"] == "jti-1"


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"now": 1301}, "expired"),
        ({"expected_audience": "payment-service"}, "audience"),
        ({"allowed_issuers": ["payment-service"]}, "issuer"),
    ],
)
def test_s2s_token_rejects_expired_wrong_audience_or_issuer(kwargs, error):
    signer = _signer()
    token = create_s2s_token(
        signer=signer,
        issuer="user-service",
        subject="user-service",
        audience="resource-service",
        tenant_id="tenant-alpha",
        now=1000,
    )

    verify_kwargs = {
        "signer": signer,
        "expected_audience": "resource-service",
        "allowed_issuers": ["user-service"],
        "now": 1001,
    }
    verify_kwargs.update(kwargs)

    with pytest.raises(S2STokenError, match=error):
        verify_s2s_token(token, **verify_kwargs)


def test_s2s_token_rejects_tampered_payload():
    signer = _signer()
    token = create_s2s_token(
        signer=signer,
        issuer="user-service",
        subject="user-service",
        audience="resource-service",
        tenant_id="tenant-alpha",
        now=1000,
    )
    header, payload, signature = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims["tenant_id"] = "tenant-beta"
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


def test_s2s_token_rejects_malformed_token():
    with pytest.raises(S2STokenError, match="format"):
        verify_s2s_token(
            "not-a-token",
            signer=_signer(),
            expected_audience="resource-service",
            allowed_issuers=["user-service"],
        )
