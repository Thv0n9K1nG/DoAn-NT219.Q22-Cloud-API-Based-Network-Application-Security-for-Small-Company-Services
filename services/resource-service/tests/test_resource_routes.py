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
ALPHA_RESOURCE = UUID("aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa")
BETA_RESOURCE = UUID("bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb")


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


def current_user(*, roles: tuple[str, ...], tenant_id: UUID = ALPHA_TENANT, user_id: str = "kc-alpha-user") -> CurrentUser:
    return CurrentUser(
        user_id=user_id,
        tenant_id=str(tenant_id),
        email="user@example.com",
        roles=roles,
        jti="test-jti",
        claims={},
    )


def resource(*, resource_id: UUID = ALPHA_RESOURCE, tenant_id: UUID = ALPHA_TENANT):
    return SimpleNamespace(
        id=resource_id,
        tenant_id=tenant_id,
        owner_user_id="kc-alpha-user",
        name="alpha-secret",
        data={"classification": "confidential"},
        url=None,
        created_at=datetime.now(UTC),
    )


def client_with_user(user: CurrentUser, fake_service):
    app, routes, database = load_app_and_routes()

    async def override_user():
        return user

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[database.get_db] = lambda: object()
    routes.ResourceService = lambda _: fake_service
    return TestClient(app)


def test_alpha_user_create_resource_sets_tenant_from_jwt():
    class FakeResourceService:
        async def create_resource(self, *, resource_data, tenant_id, owner_user_id):
            assert tenant_id == ALPHA_TENANT
            assert owner_user_id == "kc-alpha-user"
            assert not hasattr(resource_data, "tenant_id")
            return resource(tenant_id=tenant_id)

    client = client_with_user(current_user(roles=("tenant_user",)), FakeResourceService())

    response = client.post(
        "/api/v1/resources",
        json={"name": "alpha-secret", "data": {"classification": "confidential"}},
    )

    assert response.status_code == 201
    assert response.json()["tenant_id"] == str(ALPHA_TENANT)


def test_alpha_user_list_resources_does_not_include_beta_resource():
    class FakeResourceService:
        async def list_resources(self, *, tenant_id, include_all=False):
            assert tenant_id == ALPHA_TENANT
            assert include_all is False
            return [resource(tenant_id=ALPHA_TENANT)]

    client = client_with_user(current_user(roles=("tenant_user",)), FakeResourceService())

    response = client.get("/api/v1/resources")

    assert response.status_code == 200
    tenants = {item["tenant_id"] for item in response.json()}
    assert tenants == {str(ALPHA_TENANT)}


def test_beta_user_get_alpha_resource_returns_403_and_logs_bola(capsys):
    class FakeResourceService:
        async def get_resource(self, resource_id):
            assert resource_id == ALPHA_RESOURCE
            return resource(resource_id=ALPHA_RESOURCE, tenant_id=ALPHA_TENANT)

    client = client_with_user(
        current_user(roles=("tenant_user",), tenant_id=BETA_TENANT, user_id="kc-beta-user"),
        FakeResourceService(),
    )

    response = client.get(f"/api/v1/resources/{ALPHA_RESOURCE}")

    assert response.status_code == 403
    captured = capsys.readouterr().out
    assert '"event": "security.bola_attempt"' in captured
    assert f'"attacker_tenant_id": "{BETA_TENANT}"' in captured
    assert f'"resource_tenant_id": "{ALPHA_TENANT}"' in captured


def test_alpha_tenant_admin_can_delete_alpha_resource():
    class FakeResourceService:
        deleted = False

        async def get_resource(self, resource_id):
            assert resource_id == ALPHA_RESOURCE
            return resource(resource_id=ALPHA_RESOURCE, tenant_id=ALPHA_TENANT)

        async def delete_resource(self, *, resource):
            self.deleted = True

    fake_service = FakeResourceService()
    client = client_with_user(current_user(roles=("tenant_admin",)), fake_service)

    response = client.delete(f"/api/v1/resources/{ALPHA_RESOURCE}")

    assert response.status_code == 204
    assert fake_service.deleted is True


def test_alpha_tenant_user_cannot_delete_resource():
    class FakeResourceService:
        async def get_resource(self, _):
            raise AssertionError("service should not be called")

    client = client_with_user(current_user(roles=("tenant_user",)), FakeResourceService())

    response = client.delete(f"/api/v1/resources/{BETA_RESOURCE}")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCESS_DENIED"
