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


def test_cross_tenant_resource_read_returns_403_and_emits_bola_log(capsys):
    class FakeResourceService:
        async def get_resource(self, resource_id):
            assert resource_id == ALPHA_RESOURCE
            return SimpleNamespace(
                id=ALPHA_RESOURCE,
                tenant_id=ALPHA_TENANT,
                owner_user_id="kc-alpha-user",
                name="alpha-confidential-report",
                data={"classification": "confidential"},
                url=None,
                created_at=datetime.now(UTC),
            )

    beta_user = CurrentUser(
        user_id="kc-beta-user",
        tenant_id=str(BETA_TENANT),
        email="beta-user@example.com",
        roles=("tenant_user",),
        jti="stage16-beta-jti",
        claims={},
    )
    client = _resource_client(user=beta_user, fake_service=FakeResourceService())

    response = client.get(f"/api/v1/resources/{ALPHA_RESOURCE}")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCESS_DENIED"

    captured = capsys.readouterr().out
    assert '"event": "security.bola_attempt"' in captured
    assert f'"user_id": "{beta_user.user_id}"' in captured
    assert f'"attacker_tenant_id": "{BETA_TENANT}"' in captured
    assert f'"resource_id": "{ALPHA_RESOURCE}"' in captured
    assert f'"resource_tenant_id": "{ALPHA_TENANT}"' in captured


def _resource_client(*, user: CurrentUser, fake_service) -> TestClient:
    app, routes, database = _load_resource_app()

    async def override_user():
        return user

    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[database.get_db] = lambda: object()
    routes.ResourceService = lambda _: fake_service
    return TestClient(app)


def _load_resource_app():
    service_root = Path(__file__).resolve().parents[2] / "services" / "resource-service"
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
