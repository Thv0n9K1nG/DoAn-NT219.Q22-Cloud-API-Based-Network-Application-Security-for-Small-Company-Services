from __future__ import annotations

from shared.pqc_signing import ML_DSA_ALGORITHM, MLDSAKeyPair, MLDSASigner
from shared.webhook_signer import (
    ALGORITHM_HEADER,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    create_webhook_signature_headers,
    verify_webhook_signature,
)


def _signer() -> MLDSASigner:
    return MLDSASigner.from_keypair(MLDSAKeyPair.generate())


def test_webhook_signature_round_trip_with_canonical_json():
    signer = _signer()
    payload = {"event": "resource.updated", "data": {"id": "res-1", "tenant_id": "tenant-alpha"}}

    headers = create_webhook_signature_headers(payload, signer=signer, timestamp=1000)

    assert headers[TIMESTAMP_HEADER] == "1000"
    assert headers[ALGORITHM_HEADER] == ML_DSA_ALGORITHM
    assert headers[SIGNATURE_HEADER].startswith("mldsa65=")
    assert verify_webhook_signature(payload, headers, signer=signer, now=1001) is True
    assert verify_webhook_signature({"data": payload["data"], "event": payload["event"]}, headers, signer=signer, now=1001)


def test_webhook_signature_rejects_tampered_payload_and_signature_prefix():
    signer = _signer()
    payload = {"event": "billing.updated", "data": {"amount": 1000}}
    headers = create_webhook_signature_headers(payload, signer=signer, timestamp=1000)

    assert verify_webhook_signature({"event": "billing.updated", "data": {"amount": 9999}}, headers, signer=signer, now=1001) is False

    bad_headers = dict(headers)
    bad_headers[SIGNATURE_HEADER] = bad_headers[SIGNATURE_HEADER].replace("mldsa65=", "sha256=", 1)
    assert verify_webhook_signature(payload, bad_headers, signer=signer, now=1001) is False


def test_webhook_signature_rejects_replay_or_wrong_algorithm():
    signer = _signer()
    payload = {"event": "resource.deleted", "data": {"id": "res-1"}}
    headers = create_webhook_signature_headers(payload, signer=signer, timestamp=1000)

    assert verify_webhook_signature(payload, headers, signer=signer, now=1301) is False

    bad_headers = dict(headers)
    bad_headers[ALGORITHM_HEADER] = "HMAC-SHA256"
    assert verify_webhook_signature(payload, bad_headers, signer=signer, now=1001) is False
