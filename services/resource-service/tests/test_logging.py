from __future__ import annotations

import io
import json
import logging

from shared.logging_config import REDACTED, configure_logging
from shared.request_context import reset_request_context, set_request_context


def test_json_logging_includes_context_and_redacts_secrets():
    stream = io.StringIO()
    configure_logging(service_name="resource-service", stream=stream)
    tokens = set_request_context(
        request_id="req-123",
        tenant_id="11111111-1111-1111-1111-111111111111",
        user_id="kc-alpha-user",
    )

    try:
        logging.getLogger("resource-service").info(
            "Resource created",
            extra={
                "path": "/api/v1/resources",
                "method": "POST",
                "status_code": 201,
                "authorization": "Bearer raw.jwt.value",
                "stripe_secret": "sk_test_should_not_log",
            },
        )
    finally:
        reset_request_context(tokens)

    payload = json.loads(stream.getvalue())
    assert payload["service"] == "resource-service"
    assert payload["message"] == "Resource created"
    assert payload["request_id"] == "req-123"
    assert payload["tenant_id"] == "11111111-1111-1111-1111-111111111111"
    assert payload["user_id"] == "kc-alpha-user"
    assert payload["path"] == "/api/v1/resources"
    assert payload["status_code"] == 201
    assert payload["authorization"] == REDACTED
    assert payload["stripe_secret"] == REDACTED
    assert "raw.jwt.value" not in stream.getvalue()
    assert "sk_test_should_not_log" not in stream.getvalue()

