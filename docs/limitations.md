# Limitations

This document starts with known design trade-offs from the project specification.
It will be updated with implementation-specific limitations in later stages.

## Classical TLS

TLS uses classical cryptography in this prototype. ML-DSA is used only at the
application layer for service-to-service tokens and outbound webhook signatures.
Stage 11 uses RSA certificates and classical TLS handshakes; it does not provide
post-quantum TLS.

## Upstream TLS Versus Full mTLS

Stage 11 implements HTTPS from Kong to FastAPI upstreams with Kong-side CA
verification of each service certificate. This proves encrypted upstream traffic
and service certificate trust in the lab. It is not full mutual TLS because the
FastAPI services do not require or validate a Kong client certificate yet.
Full mTLS remains a target design item for a hardened deployment.

## Vault Dev Mode

Vault dev mode is acceptable for the lab only. A production deployment would need
HA storage, unseal strategy, policies, audit logs, and key lifecycle controls.
Stage 12 binds Vault to `127.0.0.1:8200` so local key-generation scripts can
write ML-DSA keys; this host exposure is development-only.

## Single Keycloak Realm

The design uses one Keycloak realm with tenant organizations. This is simpler to
operate, but weaker than per-tenant realms. Services must still enforce tenant
isolation independently.

## Self-Signed Certificates

Certificates under `gateway/certs/` are lab placeholders and must not be treated
as production trust material. Generated certificates and private keys under
`gateway/certs/` and `services/*/certs/` are intentionally ignored by Git.

## Stripe Inbound Webhooks

Stripe inbound webhooks use Stripe's HMAC-SHA256 signature scheme. ML-DSA is for
outbound webhooks emitted by this platform, not for replacing Stripe's inbound
verification.

## ML-DSA Application Layer Scope

Stage 12 uses real ML-DSA-65 through the Python `pqcrypto` package. Keys are
stored in Vault KV v2 and are loaded by application code for S2S tokens and
outbound webhook signatures. This does not provide post-quantum TLS, and it does
not replace Keycloak RS256 access tokens or Stripe's inbound HMAC scheme.

The lab stores ML-DSA private keys in Vault KV v2 for demonstrability. A hardened
deployment should define key rotation windows, minimize service read access to
private signing material, and prefer an HSM/KMS-backed signing interface when
available.

## Docker Compose Prototype

Docker Compose is used for repeatable local demonstration. It is not a highly
available production deployment model.
