"""Validate Stage 4 Keycloak lab tokens without verifying signatures.

Signature verification belongs in Stage 5 shared security middleware. This test
only checks that Keycloak emits the claims needed by downstream services.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.parse
import urllib.request


KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:18080")
REALM = os.getenv("KEYCLOAK_REALM", "saas-platform")
PASSWORD = os.getenv("KEYCLOAK_LAB_USER_PASSWORD", "TestPass123!")
CLIENT_ID = os.getenv("KEYCLOAK_TEST_CLIENT_ID", "saas-spa")


def fetch_token(username: str) -> str:
    payload = urllib.parse.urlencode(
        {
            "grant_type": "password",
            "client_id": CLIENT_ID,
            "username": username,
            "password": PASSWORD,
            "scope": "openid profile email",
        }
    ).encode()
    request = urllib.request.Request(
        f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)["access_token"]


def decode_payload(token: str) -> dict:
    payload = token.split(".")[1]
    payload += "=" * ((4 - len(payload) % 4) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def assert_token(username: str, tenant_id: str, role: str) -> None:
    claims = decode_payload(fetch_token(username))
    audience = claims.get("aud", [])
    if isinstance(audience, str):
        audience = [audience]

    assert claims["tenant_id"] == tenant_id, claims
    assert "saas-api" in audience, claims
    assert role in claims.get("realm_access", {}).get("roles", []), claims
    assert claims.get("exp"), claims
    assert claims.get("jti"), claims
    print(f"{username}: OK")


def assert_jwks() -> None:
    with urllib.request.urlopen(
        f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/certs",
        timeout=15,
    ) as response:
        jwks = json.load(response)
    assert jwks.get("keys"), jwks
    print("jwks: OK")


if __name__ == "__main__":
    assert_token("alpha-user@example.com", "11111111-1111-1111-1111-111111111111", "tenant_user")
    assert_token("beta-admin@example.com", "22222222-2222-2222-2222-222222222222", "tenant_admin")
    assert_jwks()
