"""Request-scoped context used by logs, errors, and DB tenant guards."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from shared.config import Settings, get_settings


request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
tenant_id_var: ContextVar[str | None] = ContextVar("tenant_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)


@dataclass(frozen=True)
class ContextTokens:
    request_id: Token[str | None]
    tenant_id: Token[str | None]
    user_id: Token[str | None]


def get_request_id() -> str | None:
    return request_id_var.get()


def get_tenant_id() -> str | None:
    return tenant_id_var.get()


def get_user_id() -> str | None:
    return user_id_var.get()


def set_request_context(
    *,
    request_id: str | None = None,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> ContextTokens:
    return ContextTokens(
        request_id=request_id_var.set(request_id),
        tenant_id=tenant_id_var.set(tenant_id),
        user_id=user_id_var.set(user_id),
    )


def reset_request_context(tokens: ContextTokens) -> None:
    request_id_var.reset(tokens.request_id)
    tenant_id_var.reset(tokens.tenant_id)
    user_id_var.reset(tokens.user_id)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Capture correlation headers while keeping JWT claims authoritative."""

    def __init__(self, app, settings: Settings | None = None):
        super().__init__(app)
        self.settings = settings or get_settings()

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(self.settings.request_id_header) or str(uuid4())
        tokens = set_request_context(
            request_id=request_id,
            tenant_id=request.headers.get(self.settings.tenant_id_header),
            user_id=request.headers.get(self.settings.user_id_header),
        )
        try:
            response = await call_next(request)
            response.headers[self.settings.request_id_header] = request_id
            return response
        finally:
            reset_request_context(tokens)

