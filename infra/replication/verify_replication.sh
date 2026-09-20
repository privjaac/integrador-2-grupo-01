#!/usr/bin/env bash
set -euo pipefail

PRIMARY_PORT="${PRIMARY_PORT:-55432}"
REPLICA_PORT="${REPLICA_PORT:-55433}"
DB_NAME="${DB_NAME:-elisa}"
DB_USER="${DB_USER:-elisa_app}"
: "${DB_PASSWORD:?Define DB_PASSWORD antes de ejecutar este script}"

export PGPASSWORD="$DB_PASSWORD"
probe="probe_$(date +%s)_$$"

primary_recovery="$(psql -At -h 127.0.0.1 -p "$PRIMARY_PORT" -U "$DB_USER" -d "$DB_NAME" -c 'SELECT pg_is_in_recovery();')"
replica_recovery="$(psql -At -h 127.0.0.1 -p "$REPLICA_PORT" -U "$DB_USER" -d "$DB_NAME" -c 'SELECT pg_is_in_recovery();')"

psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -p "$PRIMARY_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL >/dev/null
CREATE TABLE IF NOT EXISTS replication_probe (
  probe_id text PRIMARY KEY,
  created_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO replication_probe (probe_id) VALUES ('$probe');
SQL

replicated=""
for _ in {1..50}; do
  replicated="$(psql -At -h 127.0.0.1 -p "$REPLICA_PORT" -U "$DB_USER" -d "$DB_NAME" \
    -c "SELECT probe_id FROM replication_probe WHERE probe_id = '$probe';" 2>/dev/null || true)"
  [[ "$replicated" == "$probe" ]] && break
  sleep 0.1
done

if [[ "$primary_recovery" != "f" || "$replica_recovery" != "t" || "$replicated" != "$probe" ]]; then
  echo "Validación fallida: primary_recovery=$primary_recovery replica_recovery=$replica_recovery replicated=$replicated" >&2
  exit 1
fi

if psql -h 127.0.0.1 -p "$REPLICA_PORT" -U "$DB_USER" -d "$DB_NAME" \
  -c "UPDATE replication_probe SET created_at = now() WHERE probe_id = '$probe';" >/dev/null 2>&1; then
  echo "Validación fallida: la réplica aceptó una escritura." >&2
  exit 1
fi

state="$(PGPASSWORD= psql -At -p "$PRIMARY_PORT" -U postgres -d postgres \
  -c "SELECT state || '/' || sync_state FROM pg_stat_replication LIMIT 1;")"
lag_bytes="$(PGPASSWORD= psql -At -p "$PRIMARY_PORT" -U postgres -d postgres \
  -c "SELECT COALESCE(pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn), 0)::bigint FROM pg_stat_replication LIMIT 1;")"

echo "primary pg_is_in_recovery=$primary_recovery"
echo "replica pg_is_in_recovery=$replica_recovery"
echo "replication state=$state"
echo "replication lag_bytes=$lag_bytes"
echo "probe replicated=$probe"
echo "replica write rejected=true"
