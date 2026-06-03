#!/bin/bash
set -euo pipefail

POSTGRES_USER="${POSTGRES_USER:-postgres}"

apply_db() {
  local db="$1"
  local rls="${2:-false}"

  echo "Applying schema to $db..."
  docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$db" < scripts/db-init.sql >/dev/null

  if [[ "$rls" == "true" ]]; then
    echo "Applying RLS policy to $db..."
    docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$db" < scripts/apply-rls.sql >/dev/null
  fi

  echo "Seeding $db..."
  docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$db" < scripts/seed-data.sql >/dev/null
}

apply_db userdb false
apply_db resourcedb true
apply_db admindb false
apply_db paymentdb false

echo "Lab schemas and seed data are ready."
