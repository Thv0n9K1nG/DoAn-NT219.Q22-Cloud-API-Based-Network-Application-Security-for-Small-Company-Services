"""JWT verification and role dependencies for FastAPI services."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

import httpx
import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from shared.config import Settings, get_settings
from shared.errors import APIError, ErrorCode
from shared.request_context import set_request_context


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    tenant_id: str | None
    email: str | None
    roles: tuple[str, ...]
    jti: str
    claims: dict


class JWKSCache:
    """Small TTL cache that refreshes immediately when a token uses a new kid."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._jwks: dict | None = None
        self._expires_at = 0.0

    async def get_key(self, kid: str):
        jwks = await self._get_jwks()
        key = self._find_key(jwks, kid)
        if key is None:
            jwks = await self.refresh()
            key = self._find_key(jwks, kid)

        if key is None:
            raise APIError(401, ErrorCode.INVALID_TOKEN, "Unknown token signing key")

        return jwt.algorithms.RSAAlgorithm.from_jwk(key)

    async def _get_jwks(self) -> dict:
        if self._jwks is None or time.time() >= self._expires_at:
            return await self.refresh()
        return self._jwks

    async def refresh(self) -> dict:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(self.settings.jwks_url)
            response.raise_for_status()

        self._jwks = response.json()
        self._expires_at = time.time() + self.settings.jwks_cache_ttl_seconds
        return self._jwks

    @staticmethod
    def _find_key(jwks: dict, kid: str) -> str | None:
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                return json.dumps(key)
        return None


async def verify_jwt_token(
    token: str,
    *,
    settings: Settings | None = None,
    jwks_cache: JWKSCache | None = None,
) -> CurrentUser:
    settings = settings or get_settings()
    jwks_cache = jwks_cache or JWKSCache(settings)

    try:
        header = jwt.get_unverified_header(token)
        kid = header["kid"]
        public_key = await jwks_cache.get_key(kid)
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "jti", "sub"]},
        )
    except APIError:
        raise
    except jwt.ExpiredSignatureError as exc:
        raise APIError(401, ErrorCode.INVALID_TOKEN, "Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise APIError(401, ErrorCode.INVALID_TOKEN, "Invalid token") from exc
    except (KeyError, httpx.HTTPError) as exc:
        raise APIError(401, ErrorCode.INVALID_TOKEN, "Unable to validate token") from exc

    roles = tuple(claims.get("realm_access", {}).get("roles", []))
    return CurrentUser(
        user_id=claims["sub"],
        tenant_id=claims.get("tenant_id"),
        email=claims.get("email"),
        roles=roles,
        jti=claims["jti"],
        claims=claims,
    )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    if credentials is None:
        raise APIError(401, ErrorCode.AUTH_REQUIRED, "Authorization bearer token is required")

    settings = getattr(request.app.state, "settings", get_settings())
    jwks_cache = getattr(request.app.state, "jwks_cache", None)
    user = await verify_jwt_token(credentials.credentials, settings=settings, jwks_cache=jwks_cache)

    # JWT claims override any direct client headers; Kong-injected headers are correlation hints only.
    set_request_context(tenant_id=user.tenant_id, user_id=user.user_id)
    return user


def require_roles(*allowed_roles: str):
    allowed = set(allowed_roles)

    async def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if allowed.isdisjoint(user.roles):
            raise APIError(403, ErrorCode.ACCESS_DENIED, "Access denied")
        return user

    return dependency
