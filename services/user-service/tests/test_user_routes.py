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


def load_app_and_routes():
    service_root = Path(__file__).resolve().parents[1]
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]
    sys.path.insert(0, str(service_root))
    try:
        app = importlib.import_module("app.main").app
        routes = importlib.import_module("app.api.v1.routes")
        database = importlib.import_module("app.db.database")
        return app, routes, database
    finally:
        sys.path.remove(str(service_root))


def current_user(
    *,
    roles: tuple[str, ...],
    tenant_id: UUID = ALPHA_TENANT,
    user_id: str = "kc-alpha-user",
    email: str = "user@example.com",
) -> CurrentUser:
    return CurrentUser(
        user_id=user_id,
        tenant_id=str(tenant_id),
        email=email,
        roles=roles,
        jti="test-jti",
        claims={},
    )


def profile(*, tenant_id: UUID = ALPHA_TENANT, keycloak_user_id: str = "kc-alpha-user"):
    return SimpleNamespace(
        id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2"),
        keycloak_user_id=keycloak_user_id,
        tenant_id=tenant_id,
        email="alpha-user@example.com",
        role="tenant_user",
        status="active",
        created_at=datetime.now(UTC),
    )


def client_with_user(user: CurrentUser, fake_service):
    app, routes, database = load_app_and_routes()

    async def override_user():
        return user

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[database.get_db] = lambda: object()
    routes.UserService = lambda _: fake_service
    return TestClient(app)


def test_tenant_admin_lists_only_own_tenant_users():
    class FakeUserService:
        async def list_users(self, *, current_user, tenant_id=None):
            assert tenant_id is None
            assert current_user.tenant_id == str(ALPHA_TENANT)
            return [profile(tenant_id=ALPHA_TENANT)]

    client = client_with_user(current_user(roles=("tenant_admin",)), FakeUserService())

    response = client.get("/api/v1/users")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["tenant_id"] == str(ALPHA_TENANT)


def test_tenant_admin_cannot_create_user_for_another_tenant():
    class FakeUserService:
        async def create_user(self, **_):
            raise AssertionError("service should not be called")

    client = client_with_user(current_user(roles=("tenant_admin",)), FakeUserService())

    response = client.post(
        "/api/v1/users",
        json={
            "tenant_id": str(BETA_TENANT),
            "keycloak_user_id": "kc-beta-user",
            "email": "beta-user@example.com",
            "role": "tenant_user",
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCESS_DENIED"


def test_tenant_user_can_get_own_profile():
    class FakeUserService:
        async def get_user(self, user_id):
            assert user_id == "kc-alpha-user"
            return profile(keycloak_user_id="kc-alpha-user")

    client = client_with_user(current_user(roles=("tenant_user",), user_id="kc-alpha-user"), FakeUserService())

    response = client.get("/api/v1/users/kc-alpha-user")

    assert response.status_code == 200
    assert response.json()["keycloak_user_id"] == "kc-alpha-user"


def test_tenant_user_self_lookup_falls_back_to_email_when_keycloak_subject_differs():
    class FakeUserService:
        async def get_user(self, user_id):
            assert user_id == "runtime-keycloak-sub"
            return None

        async def get_user_by_email(self, *, email, tenant_id):
            assert email == "alpha-user@example.com"
            assert tenant_id == ALPHA_TENANT
            return profile(keycloak_user_id="kc-alpha-user")

    client = client_with_user(
        current_user(roles=("tenant_user",), user_id="runtime-keycloak-sub", email="alpha-user@example.com"),
        FakeUserService(),
    )

    response = client.get("/api/v1/users/runtime-keycloak-sub")

    assert response.status_code == 200
    assert response.json()["email"] == "alpha-user@example.com"


def test_tenant_user_cannot_get_beta_profile():
    class FakeUserService:
        async def get_user(self, user_id):
            assert user_id == "kc-beta-user"
            return profile(tenant_id=BETA_TENANT, keycloak_user_id="kc-beta-user")

    client = client_with_user(current_user(roles=("tenant_user",), user_id="kc-alpha-user"), FakeUserService())

    response = client.get("/api/v1/users/kc-beta-user")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCESS_DENIED"
