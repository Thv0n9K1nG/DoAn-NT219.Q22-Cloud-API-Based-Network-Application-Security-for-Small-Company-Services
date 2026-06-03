from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_kong_template() -> dict:
    text = (ROOT / "gateway/kong.template.yml").read_text(encoding="utf-8")
    text = text.replace("__KONG_JWT_ISSUER__", "http://keycloak.test/realms/saas-platform")
    text = text.replace("__KONG_JWT_PUBLIC_KEY__", "          -----BEGIN PUBLIC KEY-----\n          MIIB\n          -----END PUBLIC KEY-----")
    text = text.replace("__KONG_INTERNAL_CA_CERT__", "      -----BEGIN CERTIFICATE-----\n      MIIB\n      -----END CERTIFICATE-----")
    text = text.replace("__KONG_UPSTREAM_CLIENT_CERT__", "      -----BEGIN CERTIFICATE-----\n      MIIB\n      -----END CERTIFICATE-----")
    text = text.replace("__KONG_UPSTREAM_CLIENT_KEY__", "      -----BEGIN PRIVATE KEY-----\n      MIIB\n      -----END PRIVATE KEY-----")
    text = text.replace("__KONG_INTERNAL_MLDSA_TOKEN__", "test.mldsa.token")
    text = text.replace("__REDIS_PASSWORD__", "test-redis-password")
    return yaml.safe_load(text)


def test_opa_plugin_overwrites_tenant_header_before_rate_limiting():
    handler = (ROOT / "gateway/plugins/opa-authz/handler.lua").read_text(encoding="utf-8")

    assert 'ngx.req.set_header("X-Tenant-ID", tenant_id)' in handler
    assert 'kong.service.request.set_header("X-Tenant-ID", tenant_id)' in handler


def test_resource_route_rate_limit_uses_verified_tenant_header():
    template = load_kong_template()
    resource_service = next(service for service in template["services"] if service["name"] == "resource-service")
    resource_route = next(route for route in resource_service["routes"] if route["name"] == "resource-api")
    rate_limit = next(plugin for plugin in resource_route["plugins"] if plugin["name"] == "rate-limiting")

    assert rate_limit["config"]["limit_by"] == "header"
    assert rate_limit["config"]["header_name"] == "X-Tenant-ID"


def test_gateway_adds_baseline_no_cache_and_clickjacking_headers():
    template = load_kong_template()
    response_transformer = next(plugin for plugin in template["plugins"] if plugin["name"] == "response-transformer")
    headers = set(response_transformer["config"]["add"]["headers"])

    assert "Cache-Control:no-store" in headers
    assert "X-Content-Type-Options:nosniff" in headers
    assert "X-Frame-Options:DENY" in headers


def test_gateway_injects_internal_mldsa_assertion_and_removes_spoofed_header():
    template = load_kong_template()
    transformer = next(plugin for plugin in template["plugins"] if plugin["name"] == "request-transformer")

    assert "X-Internal-MLDSA-Token" in transformer["config"]["remove"]["headers"]
    assert "X-Internal-MLDSA-Token:test.mldsa.token" in transformer["config"]["add"]["headers"]
