"""JWT-like service token format signed with ML-DSA-65."""

from __future__ import annotations

import base64
import json
import time
import uuid
from typing import Any, Iterable

from shared.pqc_signing import ML_DSA_ALGORITHM, MLDSASigner


TOKEN_TYP = "JWT"  # nosec B105


class S2STokenError(ValueError):
    """Raised when an ML-DSA service token cannot be trusted."""


def create_s2s_token(
    *,
    signer: MLDSASigner,
    issuer: str,
    subject: str,
    audience: str,
    tenant_id: str,
    ttl_seconds: int = 300,
    now: int | None = None,
    jti: str | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    issued_at = int(now if now is not None else time.time())
    payload: dict[str, Any] = {
        "iss": issuer,
        "sub": subject,
        "aud": audience,
        "iat": issued_at,
        "exp": issued_at + ttl_seconds,
        "jti": jti or str(uuid.uuid4()),
        "tenant_id": tenant_id,
    }
    if extra_claims:
        protected_claims = set(payload)
        overlap = protected_claims.intersection(extra_claims)
        if overlap:
            raise S2STokenError(f"extra_claims cannot override protected claims: {sorted(overlap)}")
        payload.update(extra_claims)

    header = {"alg": ML_DSA_ALGORITHM, "typ": TOKEN_TYP}
    signing_input = f"{_b64url_json(header)}.{_b64url_json(payload)}".encode("ascii")
    signature = _b64url_from_b64(signer.sign(signing_input))
    return f"{signing_input.decode('ascii')}.{signature}"


def verify_s2s_token(
    token: str,
    *,
    signer: MLDSASigner,
    expected_audience: str,
    allowed_issuers: Iterable[str],
    now: int | None = None,
) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3 or not all(parts):
        raise S2STokenError("Invalid S2S token format")

    header = _json_from_b64url(parts[0], "header")
    if header.get("alg") != ML_DSA_ALGORITHM or header.get("typ") != TOKEN_TYP:
        raise S2STokenError("Unsupported S2S token header")

    payload = _json_from_b64url(parts[1], "payload")
    try:
        signature_b64 = _b64_from_b64url(parts[2])
    except Exception as exc:
        raise S2STokenError("Invalid S2S token signature encoding") from exc
    signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")

    if not signer.verify(signing_input, signature_b64):
        raise S2STokenError("Invalid S2S token signature")

    required = {"iss", "sub", "aud", "iat", "exp", "jti", "tenant_id"}
    missing = sorted(required.difference(payload))
    if missing:
        raise S2STokenError(f"S2S token missing required claims: {missing}")

    try:
        expires_at = int(payload["exp"])
    except (TypeError, ValueError) as exc:
        raise S2STokenError("S2S token exp must be an integer timestamp") from exc

    current_time = int(now if now is not None else time.time())
    if expires_at <= current_time:
        raise S2STokenError("S2S token is expired")
    if payload.get("aud") != expected_audience:
        raise S2STokenError("S2S token audience mismatch")
    if payload.get("iss") not in set(allowed_issuers):
        raise S2STokenError("S2S token issuer is not allowed")

    return payload


def _b64url_json(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _b64url_encode(encoded)


def _json_from_b64url(value: str, label: str) -> dict[str, Any]:
    try:
        decoded = base64.urlsafe_b64decode(_pad_b64(value)).decode("utf-8")
        parsed = json.loads(decoded)
    except Exception as exc:
        raise S2STokenError(f"Invalid S2S token {label}") from exc
    if not isinstance(parsed, dict):
        raise S2STokenError(f"Invalid S2S token {label}")
    return parsed


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_from_b64(value: str) -> str:
    return _b64url_encode(base64.b64decode(value, validate=True))


def _b64_from_b64url(value: str) -> str:
    return base64.b64encode(base64.urlsafe_b64decode(_pad_b64(value))).decode("ascii")


def _pad_b64(value: str) -> str:
    return value + "=" * (-len(value) % 4)
