# Preliminary Threat Model

This document captures the Stage 1 STRIDE baseline. Later stages will refine it
with implemented controls, test evidence, and residual risk.

## Scope

In scope:

- Client-to-API authentication and authorization.
- Tenant isolation across users, resources, payments, and admin actions.
- Gateway, service, database, and observability boundaries.
- Secret storage, signing keys, and application-layer ML-DSA usage.
- Webhook handling for Stripe inbound events and outbound platform events.

Out of scope for this prototype:

- Production high availability.
- Post-quantum TLS handshakes.
- Real card processing outside Stripe sandbox.
- Testing systems outside the local lab.

## Trust Boundaries

| Boundary | Description | Primary Controls |
| --- | --- | --- |
| Internet to DMZ | External clients reach Kong only | TLS, JWT validation, rate limiting, WAF-lite |
| DMZ to app network | Kong routes to OPA and services | Route allowlist, service headers, future mTLS |
| App to data network | Services reach PostgreSQL, Redis, Loki | Network segmentation, DB credentials, RLS |
| Services to Vault | Services retrieve secrets and keys | Vault policies, AppRole in later stages |
| Stripe to payment service | Stripe sends payment webhooks | Stripe HMAC verification |

## STRIDE Summary

| Threat | Vector | Planned Mitigation |
| --- | --- | --- |
| Spoofing | Fake JWT, token forgery, fake service identity | Keycloak RS256 JWT, Kong JWT validation, short token TTL, ML-DSA S2S signing |
| Tampering | Modified payload, forged webhook, MITM inside lab network | TLS, request schema validation, Stripe HMAC, ML-DSA outbound webhook signatures |
| Repudiation | User denies API action or admin change | Structured logs, request ID, tenant ID, user ID, audit events |
| Information Disclosure | BOLA, excessive response fields, cross-tenant reads | OPA authz, service tenant checks, DTO filtering, PostgreSQL RLS |
| Denial of Service | Brute force, scraping, noisy tenant, webhook flood | Kong rate limiting, Redis counters, WAF-lite rules, service timeouts |
| Elevation of Privilege | Role claim manipulation, IDOR, unsafe admin route | Verified JWT claims, RBAC/ABAC policy, admin IP restriction, service-side checks |

## OWASP API Top 10 Mapping

| Risk | Planned Control |
| --- | --- |
| API1 BOLA | OPA policy plus service-level tenant ownership check |
| API2 Broken Authentication | Keycloak OIDC, short-lived access tokens, refresh-token controls |
| API3 Broken Object Property Level Authorization | Pydantic DTOs and response filtering |
| API4 Unrestricted Resource Consumption | Kong rate limits and service request limits |
| API5 Broken Function Level Authorization | RBAC/ABAC policy in OPA and service guards |
| API6 SSRF | URL validation and metadata/internal address denylist |
| API7 Security Misconfiguration | Compose network segmentation, least exposed ports, no default secrets |
| API8 Automated Threats | Rate limiting, structured detection logs, alerts |
| API9 Improper Inventory Management | Versioned `/api/v1` routes and OpenAPI specs |
| API10 Unsafe Consumption of APIs | Stripe SDK verification, timeouts, strict webhook verification |

## Stage 1 Residual Risk

Stage 1 only creates the repository skeleton and planning documents. Controls are
not active until later implementation stages. The current risk is acceptable only
because no runtime service is exposed yet.
