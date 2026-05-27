"""Structured JSON logging with request context and secret redaction."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import TextIO

from shared.request_context import get_request_id, get_tenant_id, get_user_id


REDACTED = "[REDACTED]"
SENSITIVE_KEY_PARTS = ("authorization", "token", "password", "secret", "api_key")
STANDARD_LOG_RECORD_KEYS = set(logging.makeLogRecord({}).__dict__)


def _redact_value(key: str, value):
    if any(part in key.lower() for part in SENSITIVE_KEY_PARTS):
        return REDACTED
    return value


class JsonFormatter(logging.Formatter):
    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
            "tenant_id": get_tenant_id(),
            "user_id": get_user_id(),
        }

        for key, value in record.__dict__.items():
            if key not in STANDARD_LOG_RECORD_KEYS and not key.startswith("_"):
                payload[key] = _redact_value(key, value)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(
    *,
    service_name: str,
    log_level: str = "INFO",
    stream: TextIO | None = None,
) -> None:
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(JsonFormatter(service_name))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level.upper())

