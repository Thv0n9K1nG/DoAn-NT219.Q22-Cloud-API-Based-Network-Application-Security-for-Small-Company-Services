from pathlib import Path
import importlib
import sys

from fastapi.testclient import TestClient


def load_app():
    service_root = Path(__file__).resolve().parents[1]
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]
    sys.path.insert(0, str(service_root))
    try:
        return importlib.import_module("app.main").app
    finally:
        sys.path.remove(str(service_root))


def test_live_health():
    client = TestClient(load_app())

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["service"] == "user-service"

