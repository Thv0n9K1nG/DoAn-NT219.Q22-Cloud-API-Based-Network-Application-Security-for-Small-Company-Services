"""Outbound webhook signing with canonical JSON and ML-DSA-65."""

from __future__ import annotations

import json
import time
from typing import Any, Mapping

from shared.pqc_signing import ML_DSA_ALGORITHM, MLDSASigner


TIMESTAMP_HEADER = "X-Webhook-Timestamp"
SIGNATURE_HEADER = "X-Webhook-Signature"
ALGORITHM_HEADER = "X-Webhook-Algorithm"
SIGNATURE_PREFIX = "mldsa65="
DEFAULT_REPLAY_TOLERANCE_SECONDS = 300


class WebhookSignatureError(ValueError):
    """Raised when an outbound webhook signature fails validation."""


def canonical_json_bytes(payload: Any) -> bytes:
    """Serialize payloads exactly once so signing and verification agree."""

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def create_webhook_signature_headers(
    payload: Any,
    *,
    signer: MLDSASigner,
    timestamp: int | None = None,
) -> dict[str, str]:
    issued_at = int(timestamp if timestamp is not None else time.time())
    signature = signer.sign(_signed_webhook_bytes(payload, issued_at))
    return {
        TIMESTAMP_HEADER: str(issued_at),
        SIGNATURE_HEADER: f"{SIGNATURE_PREFIX}{signature}",
        ALGORITHM_HEADER: ML_DSA_ALGORITHM,
    }


def verify_webhook_signature(
    payload: Any,
    headers: Mapping[str, str],
    *,
    signer: MLDSASigner,
    now: int | None = None,
    tolerance_seconds: int = DEFAULT_REPLAY_TOLERANCE_SECONDS,
) -> bool:
    try:
        timestamp = int(headers[TIMESTAMP_HEADER])
        signature_header = headers[SIGNATURE_HEADER]
    except (KeyError, TypeError, ValueError):
        return False

    if headers.get(ALGORITHM_HEADER) != ML_DSA_ALGORITHM:
        return False

    current_time = int(now if now is not None else time.time())
    if abs(current_time - timestamp) > tolerance_seconds:
        return False
    if not signature_header.startswith(SIGNATURE_PREFIX):
        return False

    signature = signature_header.removeprefix(SIGNATURE_PREFIX)
    return signer.verify(_signed_webhook_bytes(payload, timestamp), signature)


def _signed_webhook_bytes(payload: Any, timestamp: int) -> bytes:
    # Include the timestamp in the signed bytes so replay window checks are tamper-evident.
    return f"{timestamp}.".encode("ascii") + canonical_json_bytes(payload)
