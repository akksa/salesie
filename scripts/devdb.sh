#!/usr/bin/env bash
# Private Postgres cluster for local development, kept inside the repo (.pgdata, gitignored).
# Usage: scripts/devdb.sh init|start|stop|status
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PGDATA="$ROOT/.pgdata/data"
PGRUN="$ROOT/.pgdata/run"
PGPORT="${SALESIE_PGPORT:-5433}"
PGBIN="${SALESIE_PGBIN:-$(ls -d /usr/lib/postgresql/*/bin | sort -V | tail -1)}"
ENV_FILE="$ROOT/backend/.env"

init() {
  if [[ -d "$PGDATA" ]]; then
    echo "already initialized: $PGDATA"
    return
  fi
  mkdir -p "$PGDATA" "$PGRUN"
  local password
  password="$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 24)"
  local pwfile
  pwfile="$(mktemp)"
  printf '%s' "$password" >"$pwfile"
  "$PGBIN/initdb" -D "$PGDATA" -U salesie --pwfile="$pwfile" \
    --auth-local=scram-sha-256 --auth-host=scram-sha-256 >/dev/null
  rm -f "$pwfile"
  start
  PGPASSWORD="$password" "$PGBIN/psql" -h 127.0.0.1 -p "$PGPORT" -U salesie -d postgres -q \
    -c "CREATE DATABASE salesie" -c "CREATE DATABASE salesie_test"
  if [[ ! -f "$ENV_FILE" ]]; then
    cp "$ROOT/backend/.env.example" "$ENV_FILE"
  fi
  chmod 600 "$ENV_FILE"
  sed -i "s#^DATABASE_URL=.*#DATABASE_URL=postgresql+asyncpg://salesie:${password}@127.0.0.1:${PGPORT}/salesie#" "$ENV_FILE"
  sed -i "s#^TEST_DATABASE_URL=.*#TEST_DATABASE_URL=postgresql+asyncpg://salesie:${password}@127.0.0.1:${PGPORT}/salesie_test#" "$ENV_FILE"
  echo "initialized; credentials written to backend/.env"
}

start() {
  if "$PGBIN/pg_ctl" -D "$PGDATA" status >/dev/null 2>&1; then
    echo "already running on port $PGPORT"
    return
  fi
  "$PGBIN/pg_ctl" -D "$PGDATA" -l "$ROOT/.pgdata/postgres.log" -w \
    -o "-p $PGPORT -k $PGRUN -c listen_addresses=127.0.0.1" start >/dev/null
  echo "running on 127.0.0.1:$PGPORT"
}

stop() { "$PGBIN/pg_ctl" -D "$PGDATA" -m fast stop; }
status() { "$PGBIN/pg_ctl" -D "$PGDATA" status; }

case "${1:-}" in
  init) init ;;
  start) start ;;
  stop) stop ;;
  status) status ;;
  *) echo "usage: $0 init|start|stop|status" >&2; exit 1 ;;
esac
