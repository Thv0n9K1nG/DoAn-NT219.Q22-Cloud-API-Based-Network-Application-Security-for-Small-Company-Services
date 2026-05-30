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
import stripe


WEBHOOK_SECRET = "whsec_stage13_test"


def load_app_and_dependencies():
    service_root = Path(__file__).resolve().parents[1]
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


class VerifyingFakePaymentService:
    def __init__(self):
        _, _, payment_service = load_app_and_dependencies()
        self.payment_service = payment_service
        self.verifier = payment_service.PaymentService(SimpleNamespace(), stripe_webhook_secret=WEBHOOK_SECRET)
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


def client_with_service(fake_service):
    app, dependencies, _ = load_app_and_dependencies()

    async def override_service():
        return fake_service

    app.dependency_overrides[dependencies.get_payment_service] = override_service
    return TestClient(app)


def test_stripe_webhook_rejects_forged_signature():
    fake_service = VerifyingFakePaymentService()
    client = client_with_service(fake_service)
    payload = _stripe_event_payload()

    response = client.post(
        "/webhooks/stripe",
        content=payload,
        headers={"Stripe-Signature": "t=123,v1=forged", "Content-Type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BAD_REQUEST"
    assert fake_service.processed_event_id is None


def test_stripe_webhook_accepts_valid_signature_and_processes_event():
    fake_service = VerifyingFakePaymentService()
    client = client_with_service(fake_service)
    payload = _stripe_event_payload()

    response = client.post(
        "/webhooks/stripe",
        content=payload,
        headers={"Stripe-Signature": _stripe_signature(payload, WEBHOOK_SECRET), "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "received": True,
        "event_type": "payment_intent.succeeded",
        "payment_intent_id": "pi_stage13_test",
        "duplicate": False,
        "status": "succeeded",
    }
    assert fake_service.processed_event_id == "evt_stage13_test"


def test_payment_service_verifier_uses_stripe_sdk_construct_event():
    payload = _stripe_event_payload()
    signature = _stripe_signature(payload, WEBHOOK_SECRET)
    _, _, payment_service = load_app_and_dependencies()
    service = payment_service.PaymentService(SimpleNamespace(), stripe_webhook_secret=WEBHOOK_SECRET)

    event = service.verify_stripe_event(payload, signature)

    assert isinstance(event, stripe.Event)
    assert event["id"] == "evt_stage13_test"


def _stripe_event_payload() -> bytes:
    return json.dumps(
        {
            "id": "evt_stage13_test",
            "object": "event",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_stage13_test",
                    "object": "payment_intent",
                    "amount": 2000,
                    "currency": "usd",
                    "metadata": {
                        "tenant_id": "11111111-1111-1111-1111-111111111111",
                        "user_id": "kc-alpha-user",
                    },
                }
            },
        },
        separators=(",", ":"),
    ).encode("utf-8")


def _stripe_signature(payload: bytes, secret: str) -> str:
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload.decode('utf-8')}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"
