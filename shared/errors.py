"""Consistent API error payloads without leaking stack traces."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from shared.request_context import get_request_id


class ErrorCode:
    AUTH_REQUIRED = "AUTH_REQUIRED"
    INVALID_TOKEN = "INVALID_TOKEN"  # nosec B105
    ACCESS_DENIED = "ACCESS_DENIED"
    BAD_REQUEST = "BAD_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class APIError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def error_payload(code: str, message: str, request_id: str | None = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id or get_request_id(),
        }
    }


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
        settings = getattr(getattr(request.app, "state", None), "settings", None)
        logger = logging.getLogger(getattr(settings, "service_name", "service"))
        if exc.status_code == 401:
            logger.warning(
                "security.auth_failed",
                extra={"event": "security.auth_failed", "path": request.url.path, "method": request.method, "status_code": 401},
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.code, exc.message),
        )
