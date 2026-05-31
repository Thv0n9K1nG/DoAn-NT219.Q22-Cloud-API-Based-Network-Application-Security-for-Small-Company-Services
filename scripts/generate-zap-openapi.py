"""Generate a small gateway-facing OpenAPI document for local ZAP scans."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_openapi(server_url: str) -> dict:
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "NT219 SaaS Gateway ZAP Scan",
            "version": "1.0.0",
            "description": "Gateway-facing API surface used for local OWASP ZAP API scans.",
        },
        "servers": [{"url": server_url.rstrip("/")}],
        "paths": {
            "/api/v1/resources": {
                "get": {
                    "summary": "List tenant resources",
                    "responses": {
                        "200": {"description": "Resource list"},
                        "401": {"description": "Authentication required"},
                        "403": {"description": "Access denied"},
                    },
                    "security": [{"bearerAuth": []}],
                }
            },
            "/api/v1/payments": {
                "get": {
                    "summary": "List tenant payments",
                    "responses": {
                        "200": {"description": "Payment list"},
                        "401": {"description": "Authentication required"},
                        "403": {"description": "Access denied"},
                    },
                    "security": [{"bearerAuth": []}],
                }
            },
            "/api/v1/admin/tenants": {
                "get": {
                    "summary": "List tenants",
                    "responses": {
                        "200": {"description": "Tenant list"},
                        "401": {"description": "Authentication required"},
                        "403": {"description": "Access denied"},
                    },
                    "security": [{"bearerAuth": []}],
                }
            },
            "/webhooks/stripe": {
                "post": {
                    "summary": "Stripe webhook endpoint",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "additionalProperties": True,
                                    "example": {
                                        "id": "evt_zap_smoke",
                                        "type": "payment_intent.succeeded",
                                        "data": {"object": {"id": "pi_zap_smoke"}},
                                    },
                                }
                            }
                        },
                    },
                    "parameters": [
                        {
                            "name": "Stripe-Signature",
                            "in": "header",
                            "required": False,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {"description": "Webhook accepted"},
                        "400": {"description": "Invalid Stripe signature"},
                    },
                }
            },
        },
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                }
            }
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-url", default="https://host.docker.internal:8443")
    parser.add_argument("--output", default="tests/reports/zap-openapi.json")
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build_openapi(args.server_url), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {output} server_url={args.server_url.rstrip('/')}")


if __name__ == "__main__":
    main()
