# Limitations

This document starts with known design trade-offs from the project specification.
It will be updated with implementation-specific limitations in later stages.

## Classical TLS

TLS uses classical cryptography in this prototype. ML-DSA is used only at the
application layer for service-to-service tokens and outbound webhook signatures.

## Vault Dev Mode

Vault dev mode is acceptable for the lab only. A production deployment would need
HA storage, unseal strategy, policies, audit logs, and key lifecycle controls.

## Single Keycloak Realm

The design uses one Keycloak realm with tenant organizations. This is simpler to
operate, but weaker than per-tenant realms. Services must still enforce tenant
isolation independently.

## Self-Signed Certificates

Certificates under `gateway/certs/` are lab placeholders and must not be treated
as production trust material.

## Stripe Inbound Webhooks

Stripe inbound webhooks use Stripe's HMAC-SHA256 signature scheme. ML-DSA is for
outbound webhooks emitted by this platform, not for replacing Stripe's inbound
verification.

## Docker Compose Prototype

Docker Compose is used for repeatable local demonstration. It is not a highly
available production deployment model.
