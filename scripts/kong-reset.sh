#!/bin/bash
set -euo pipefail

# Re-render the DB-less config before recreating Kong so JWT keys stay in sync with Keycloak.
bash scripts/kong-init.sh
docker compose up -d --force-recreate kong
docker compose ps kong
