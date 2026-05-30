from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID
import importlib
import sys

from fastapi.testclient import TestClient

from shared.security_middleware import CurrentUser, get_current_user


ALPHA_TENANT = UUID("11111111-1111-1111-1111-111111111111")
BETA_TENANT = UUID("22222222-2222-2222-2222-222222222222")
ALPHA_PAYMENT = UUID("dddddddd-1111-1111-1111-dddddddddddd")


def load_app_and_modules():
    service_root = Path(__file__).resolve().parents[1]
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]
    sys.path.insert(0, str(service_root))
    try:
        app = importlib.import_module("app.main").app
        dependencies = importlib.import_module("app.api.v1.dependencies")
        return app, dependencies
    finally:
        sys.path.remove(str(service_root))


def current_user(*, roles: tuple[str, ...], tenant_id: UUID = ALPHA_TENANT, user_id: str = "kc-alpha-user") -> CurrentUser:
    return CurrentUser(
        user_id=user_id,
        tenant_id=str(tenant_id),
        email="user@example.com",
        roles=roles,
        jti="test-jti",
        claims={},
    )


def payment(*, tenant_id: UUID = ALPHA_TENANT, status: str = "requires_payment_method"):
    return SimpleNamespace(
        id=ALPHA_PAYMENT,
        tenant_id=tenant_id,
        user_id="kc-alpha-user",
        stripe_payment_intent_id="pi_test_alpha",
        amount=2000,
        currency="usd",
        status=status,
        created_at=datetime.now(UTC),
    )


def client_with_service(user: CurrentUser, fake_service):
    app, dependencies = load_app_and_modules()

    async def override_user():
        return user

    async def override_service():
        return fake_service

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[dependencies.get_payment_service] = override_service
    return TestClient(app)


def test_create_payment_intent_uses_tenant_from_jwt():
    class FakePaymentService:
        async def create_payment_intent(self, *, payment_data, tenant_id, user_id):
            assert payment_data.amount == 2000
            assert payment_data.currency == "usd"
            assert tenant_id == ALPHA_TENANT
            assert user_id == "kc-alpha-user"
            assert not hasattr(payment_data, "tenant_id")
            return SimpleNamespace(payment=payment(tenant_id=tenant_id), client_secret="pi_test_secret")

    client = client_with_service(current_user(roles=("tenant_user",)), FakePaymentService())

    response = client.post("/api/v1/payments/intent", json={"amount": 2000, "currency": "USD", "tenant_id": str(BETA_TENANT)})

    assert response.status_code == 201
    assert response.json() == {
        "payment_id": str(ALPHA_PAYMENT),
        "payment_intent_id": "pi_test_alpha",
        "client_secret": "pi_test_secret",
        "status": "requires_payment_method",
    }


def test_create_payment_intent_rejects_unsupported_currency():
    class FakePaymentService:
        async def create_payment_intent(self, **_):
            raise AssertionError("service should not be called")

    client = client_with_service(current_user(roles=("tenant_user",)), FakePaymentService())

    response = client.post("/api/v1/payments/intent", json={"amount": 2000, "currency": "eur"})

    assert response.status_code == 422


def test_tenant_admin_lists_only_own_tenant_payments():
    class FakePaymentService:
        async def list_payments(self, *, tenant_id):
            assert tenant_id == ALPHA_TENANT
            return [payment(tenant_id=tenant_id, status="succeeded")]

    client = client_with_service(current_user(roles=("tenant_admin",)), FakePaymentService())

    response = client.get("/api/v1/payments")

    assert response.status_code == 200
    assert {item["tenant_id"] for item in response.json()} == {str(ALPHA_TENANT)}
    assert response.json()[0]["status"] == "succeeded"


def test_cross_tenant_payment_read_is_denied_and_logged(capsys):
    class FakePaymentService:
        async def get_payment(self, payment_id):
            assert payment_id == ALPHA_PAYMENT
            return payment(tenant_id=ALPHA_TENANT)

    client = client_with_service(current_user(roles=("tenant_user",), tenant_id=BETA_TENANT, user_id="kc-beta-user"), FakePaymentService())

    response = client.get(f"/api/v1/payments/{ALPHA_PAYMENT}")

    assert response.status_code == 403
    captured = capsys.readouterr().out
    assert '"event": "security.payment_bola_attempt"' in captured
    assert f'"attacker_tenant_id": "{BETA_TENANT}"' in captured
