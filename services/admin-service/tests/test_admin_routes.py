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


def current_user(*, roles: tuple[str, ...]) -> CurrentUser:
    return CurrentUser(
        user_id="kc-platform-admin",
        tenant_id=str(ALPHA_TENANT),
        email="platform-admin@example.com",
        roles=roles,
        jti="test-jti",
        claims={},
    )


def client_with_user(user: CurrentUser, fake_service):
    app, routes, database = load_app_and_routes()

    async def override_user():
        return user

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[database.get_db] = lambda: object()
    routes.AdminService = lambda _: fake_service
    return TestClient(app)


def tenant():
    return SimpleNamespace(
        id=ALPHA_TENANT,
        name="tenant-alpha",
        status="active",
        created_at=datetime.now(UTC),
    )


def test_platform_admin_can_list_tenants():
    class FakeAdminService:
        async def list_tenants(self):
            return [tenant()]

    client = client_with_user(current_user(roles=("platform_admin",)), FakeAdminService())

    response = client.get("/api/v1/admin/tenants")

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(ALPHA_TENANT)


def test_non_platform_admin_cannot_list_tenants():
    class FakeAdminService:
        async def list_tenants(self):
            raise AssertionError("service should not be called")

    client = client_with_user(current_user(roles=("tenant_admin",)), FakeAdminService())

    response = client.get("/api/v1/admin/tenants")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCESS_DENIED"


def test_platform_admin_can_onboard_tenant_and_rotate_key():
    class FakeAdminService:
        async def create_tenant(self, tenant_data):
            assert tenant_data.name == "tenant-alpha"
            return tenant()

        async def rotate_tenant_key(self, tenant_id):
            assert tenant_id == ALPHA_TENANT
            return f"tenant-{tenant_id}"

    client = client_with_user(current_user(roles=("platform_admin",)), FakeAdminService())

    create_response = client.post("/api/v1/admin/tenants", json={"name": "tenant-alpha"})
    rotate_response = client.post(f"/api/v1/admin/tenants/{ALPHA_TENANT}/keys")

    assert create_response.status_code == 201
    assert rotate_response.status_code == 200
    assert rotate_response.json()["new_key_name"] == f"tenant-{ALPHA_TENANT}"


def test_platform_admin_can_read_tenant_stats():
    class FakeAdminService:
        async def tenant_stats(self, tenant_id):
            assert tenant_id == ALPHA_TENANT
            return {"users": 2, "resources": 1, "payments": 1}

    client = client_with_user(current_user(roles=("platform_admin",)), FakeAdminService())

    response = client.get(f"/api/v1/admin/tenants/{ALPHA_TENANT}/stats")

    assert response.status_code == 200
    assert response.json() == {
        "tenant_id": str(ALPHA_TENANT),
        "users": 2,
        "resources": 1,
        "payments": 1,
    }
