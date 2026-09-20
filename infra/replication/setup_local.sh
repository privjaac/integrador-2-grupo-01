#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="${REPLICATION_RUNTIME_DIR:-$SCRIPT_DIR/.runtime}"
PRIMARY_DIR="$RUNTIME_DIR/primary"
REPLICA_DIR="$RUNTIME_DIR/replica"
PRIMARY_PORT="${PRIMARY_PORT:-55432}"
REPLICA_PORT="${REPLICA_PORT:-55433}"
DB_NAME="${DB_NAME:-elisa}"
DB_USER="${DB_USER:-elisa_app}"
REPLICATION_USER="${REPLICATION_USER:-replicator}"

: "${DB_PASSWORD:?Define DB_PASSWORD antes de ejecutar este script}"
: "${REPLICATION_PASSWORD:?Define REPLICATION_PASSWORD antes de ejecutar este script}"

PG_BINDIR="${PG_BINDIR:-$(pg_config --bindir)}"
export PATH="$PG_BINDIR:$PATH"

if [[ -e "$PRIMARY_DIR/PG_VERSION" || -e "$REPLICA_DIR/PG_VERSION" ]]; then
  echo "Ya existe un laboratorio en $RUNTIME_DIR. Ejecuta stop_local.sh --clean para reiniciarlo." >&2
  exit 1
fi

mkdir -p "$RUNTIME_DIR"
initdb -D "$PRIMARY_DIR" --username=postgres --auth-local=trust --auth-host=scram-sha-256 >/dev/null

cat >>"$PRIMARY_DIR/postgresql.conf" <<EOF
listen_addresses = '127.0.0.1'
port = $PRIMARY_PORT
wal_level = replica
max_wal_senders = 10
max_replication_slots = 10
wal_keep_size = '128MB'
hot_standby = on
password_encryption = 'scram-sha-256'
EOF

cat >>"$PRIMARY_DIR/pg_hba.conf" <<EOF
host replication $REPLICATION_USER 127.0.0.1/32 scram-sha-256
host $DB_NAME $DB_USER 127.0.0.1/32 scram-sha-256
EOF

pg_ctl -D "$PRIMARY_DIR" -l "$RUNTIME_DIR/primary.log" start >/dev/null

cleanup_on_error() {
  pg_ctl -D "$REPLICA_DIR" stop -m fast >/dev/null 2>&1 || true
  pg_ctl -D "$PRIMARY_DIR" stop -m fast >/dev/null 2>&1 || true
}
trap cleanup_on_error ERR

psql -v ON_ERROR_STOP=1 -p "$PRIMARY_PORT" -U postgres \
  -v db_name="$DB_NAME" -v db_user="$DB_USER" -v db_password="$DB_PASSWORD" \
  -v repl_user="$REPLICATION_USER" -v repl_password="$REPLICATION_PASSWORD" <<'SQL' >/dev/null
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'repl_user', :'repl_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'repl_user') \gexec
SELECT format('ALTER ROLE %I WITH REPLICATION', :'repl_user') \gexec
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'db_user', :'db_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'db_user') \gexec
SELECT format('CREATE DATABASE %I OWNER %I', :'db_name', :'db_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db_name') \gexec
SQL

PGPASSWORD="$REPLICATION_PASSWORD" pg_basebackup \
  -h 127.0.0.1 -p "$PRIMARY_PORT" -U "$REPLICATION_USER" \
  -D "$REPLICA_DIR" -Fp -Xs -P -R >/dev/null

cat >>"$REPLICA_DIR/postgresql.conf" <<EOF
port = $REPLICA_PORT
hot_standby = on
EOF

pg_ctl -D "$REPLICA_DIR" -l "$RUNTIME_DIR/replica.log" start >/dev/null
trap - ERR

echo "Primary: 127.0.0.1:$PRIMARY_PORT"
echo "Replica: 127.0.0.1:$REPLICA_PORT"
echo "Runtime: $RUNTIME_DIR"
