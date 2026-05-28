# Vault Production Notes

This lab uses Vault dev mode for repeatable local demonstration. Dev mode is not
production-safe because data is ephemeral, Vault auto-unseals, and the root token
is intentionally easy to bootstrap.

## Required Production Changes

- Use durable storage such as Integrated Storage/Raft or a managed backend.
- Enable TLS on Vault listeners and disable plaintext access.
- Configure auto-unseal through a cloud KMS or run a documented manual unseal
  process with quorum control.
- Never put the root token in `.env`, CI logs, shell history, or container args.
- Rotate AppRole `secret_id` values and use short TTLs with low use counts.
- Enable audit devices before writing production secrets.
- Separate policies by service and review them as part of change control.
- Back up Vault storage and test restore procedures.
- Treat PKI root CA material as high impact; use an intermediate CA for service
  certificate issuance.

## Lab-to-Production Gap

The current Compose deployment proves the security workflow, not availability or
operational maturity. A production deployment needs HA Vault nodes, sealed state
monitoring, audit log retention, disaster recovery, certificate lifecycle
automation, and explicit incident runbooks.
