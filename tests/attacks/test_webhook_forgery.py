from __future__ import annotations

import hashlib
import hmac
import json
import time
from pathlib import Path
from types import SimpleNamespace
import importlib
import sys

from fastapi.testclient import TestClient


WEBHOOK_SIGNING_KEY = "stage16-public-test-webhook-signing-key"


class VerifyingFakePaymentService:
    def __init__(self):
        _, _, payment_service = _load_payment_app()
        self.payment_service = payment_service
        self.verifier = payment_service.PaymentService(SimpleNamespace(), stripe_webhook_secret=WEBHOOK_SIGNING_KEY)
        self.processed_event_id = None

    def verify_stripe_event(self, payload: bytes, signature_header: str):
        return self.verifier.verify_stripe_event(payload, signature_header)

    async def process_stripe_event(self, event):
        self.processed_event_id = event["id"]
        return self.payment_service.StripeEventResult(
            event_id=event["id"],
            event_type=event["type"],
            payment_intent_id=event["data"]["object"]["id"],
            duplicate=False,
            status="succeeded",
        )


def test_stripe_webhook_forged_signature_returns_400_and_skips_processing():
    fake_service = VerifyingFakePaymentService()
    client = _payment_client(fake_service=fake_service)

    response = client.post(
        "/webhooks/stripe",
        content=_stripe_event_payload(),
        headers={"Stripe-Signature": "t=123,v1=forged", "Content-Type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"
    assert fake_service.processed_event_id is None


def test_stripe_webhook_valid_signature_is_control_case():
    fake_service = VerifyingFakePaymentService()
    client = _payment_client(fake_service=fake_service)
    payload = _stripe_event_payload()

    response = client.post(
        "/webhooks/stripe",
        content=payload,
        headers={"Stripe-Signature": _stripe_signature(payload), "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json()["received"] is True
    assert fake_service.processed_event_id == "evt_stage16_attack_test"


def _payment_client(*, fake_service) -> TestClient:
    app, dependencies, _ = _load_payment_app()

    async def override_service():
        return fake_service

    app.dependency_overrides.clear()
    app.dependency_overrides[dependencies.get_payment_service] = override_service
    return TestClient(app)


def _load_payment_app():
    service_root = Path(__file__).resolve().parents[2] / "services" / "payment-service"
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]
    sys.path.insert(0, str(service_root))
    try:
        app = importlib.import_module("app.main").app
        dependencies = importlib.import_module("app.api.v1.dependencies")
        payment_service = importlib.import_module("app.services.payment_service")
        return app, dependencies, payment_service
    finally:
        sys.path.remove(str(service_root))


def _stripe_event_payload() -> bytes:
    return json.dumps(
        {
            "id": "evt_stage16_attack_test",
            "object": "event",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_stage16_attack_test", "object": "payment_intent", "amount": 2000, "currency": "usd"}},
        },
        separators=(",", ":"),
    ).encode("utf-8")


def _stripe_signature(payload: bytes) -> str:
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload.decode('utf-8')}".encode("utf-8")
    digest = hmac.new(WEBHOOK_SIGNING_KEY.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"
