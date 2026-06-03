from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_opa_plugin_overwrites_tenant_header_before_rate_limiting():
    handler = (ROOT / "gateway/plugins/opa-authz/handler.lua").read_text(encoding="utf-8")

    assert 'ngx.req.set_header("X-Tenant-ID", tenant_id)' in handler
    assert 'kong.service.request.set_header("X-Tenant-ID", tenant_id)' in handler


def test_resource_route_rate_limit_uses_verified_tenant_header():
    template = yaml.safe_load((ROOT / "gateway/kong.template.yml").read_text(encoding="utf-8"))
    resource_service = next(service for service in template["services"] if service["name"] == "resource-service")
    resource_route = next(route for route in resource_service["routes"] if route["name"] == "resource-api")
    rate_limit = next(plugin for plugin in resource_route["plugins"] if plugin["name"] == "rate-limiting")

    assert rate_limit["config"]["limit_by"] == "header"
    assert rate_limit["config"]["header_name"] == "X-Tenant-ID"


def test_gateway_adds_baseline_no_cache_and_clickjacking_headers():
    template = yaml.safe_load((ROOT / "gateway/kong.template.yml").read_text(encoding="utf-8"))
    response_transformer = next(plugin for plugin in template["plugins"] if plugin["name"] == "response-transformer")
    headers = set(response_transformer["config"]["add"]["headers"])

    assert "Cache-Control:no-store" in headers
    assert "X-Content-Type-Options:nosniff" in headers
    assert "X-Frame-Options:DENY" in headers
