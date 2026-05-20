#!/bin/bash
set -euo pipefail

if [[ -z "${POSTGRES_MULTIPLE_DATABASES:-}" ]]; then
  echo "POSTGRES_MULTIPLE_DATABASES is empty; no extra databases to create"
  exit 0
fi

IFS=',' read -ra DBS <<< "$POSTGRES_MULTIPLE_DATABASES"
for db in "${DBS[@]}"; do
  db_trimmed="$(echo "$db" | xargs)"

  if [[ -z "$db_trimmed" ]]; then
    continue
  fi

  echo "Creating database if missing: $db_trimmed"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -v db_name="$db_trimmed" <<-EOSQL
    SELECT 'CREATE DATABASE ' || quote_ident(:'db_name')
    WHERE NOT EXISTS (
      SELECT FROM pg_database WHERE datname = :'db_name'
    )\gexec
EOSQL
done
