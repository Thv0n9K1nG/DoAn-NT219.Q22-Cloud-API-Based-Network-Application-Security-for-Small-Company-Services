from __future__ import annotations

from pathlib import Path
from uuid import UUID
import importlib
import sys

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from shared.security_middleware import CurrentUser, get_current_user


ALPHA_TENANT = UUID("11111111-1111-1111-1111-111111111111")
INTERNAL_URLS = [
    "http://169.254.169.254/latest/meta-data/",
    "http://metadata.google.internal/",
    "http://localhost:8200",
    "http://vault:8200",
    "http://opa:8181",
    "file:///etc/passwd",
    "http://127.0.0.1:5432",
]


@pytest.mark.parametrize("url", INTERNAL_URLS)
def test_resource_url_validator_blocks_internal_targets(url):
    ResourceCreate, _ = _load_resource_schemas()

    with pytest.raises(ValidationError):
        ResourceCreate(name="ssrf-probe", data={}, url=url)


def test_resource_url_validator_allows_public_https_url():
    ResourceCreate, ResourceUpdate = _load_resource_schemas()

    created = ResourceCreate(name="public-report", data={}, url="https://example.com/report")
    updated = ResourceUpdate(url="https://example.com/updated")

    assert str(created.url) == "https://example.com/report"
    assert str(updated.url) == "https://example.com/updated"


def test_create_resource_api_returns_422_for_internal_url():
    class FakeResourceService:
        async def create_resource(self, **_):
            raise AssertionError("SSRF payload should fail request validation before service execution")

    client = _resource_client(fake_service=FakeResourceService())

    response = client.post("/api/v1/resources", json={"name": "ssrf-probe", "data": {}, "url": "http://127.0.0.1:5432"})

    assert response.status_code == 422


def _resource_client(*, fake_service) -> TestClient:
    app, routes, database = _load_resource_app()

    async def override_user():
        return CurrentUser(
            user_id="kc-alpha-user",
            tenant_id=str(ALPHA_TENANT),
            email="alpha-user@example.com",
            roles=("tenant_user",),
            jti="stage16-alpha-jti",
            claims={},
        )

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


def _load_resource_schemas():
    service_root = Path(__file__).resolve().parents[2] / "services" / "resource-service"
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]
    sys.path.insert(0, str(service_root))
    try:
        schemas = importlib.import_module("app.models.schemas")
        return schemas.ResourceCreate, schemas.ResourceUpdate
    finally:
        sys.path.remove(str(service_root))
