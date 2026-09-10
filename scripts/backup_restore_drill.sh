#!/usr/bin/env bash
set -euo pipefail

# Restore a current backup into a temporary database in the running Postgres
# container. It never replaces the configured application database.
umask 077
drill_db="signal_ledger_restore_drill_${$}"
archive="$(mktemp "${TMPDIR:-/tmp}/signal-ledger-restore-drill.XXXXXX.dump")"

cleanup() {
  docker compose exec -T -e DRILL_DB="$drill_db" db sh -lc 'dropdb -U "$POSTGRES_USER" --if-exists "$DRILL_DB"' >/dev/null 2>&1 || true
  rm -f "$archive"
}
trap cleanup EXIT

docker compose exec -T db sh -lc 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$archive"
docker compose exec -T db sh -lc 'pg_restore --list >/dev/null' < "$archive"
docker compose exec -T -e DRILL_DB="$drill_db" db sh -lc 'createdb -U "$POSTGRES_USER" "$DRILL_DB"'
docker compose exec -T -e DRILL_DB="$drill_db" db sh -lc 'pg_restore -U "$POSTGRES_USER" -d "$DRILL_DB" --no-owner --exit-on-error' < "$archive"

source_counts="$(docker compose exec -T db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "SELECT (SELECT count(*) FROM schema_migrations), (SELECT count(*) FROM devices), (SELECT count(*) FROM observations), (SELECT count(*) FROM ingestion_jobs)"')"
restored_counts="$(docker compose exec -T -e DRILL_DB="$drill_db" db sh -lc 'psql -U "$POSTGRES_USER" -d "$DRILL_DB" -Atqc "SELECT (SELECT count(*) FROM schema_migrations), (SELECT count(*) FROM devices), (SELECT count(*) FROM observations), (SELECT count(*) FROM ingestion_jobs)"')"
if [[ "$source_counts" != "$restored_counts" ]]; then
  printf 'Restore drill failed: schema or operational row counts differ.\n' >&2
  exit 1
fi
printf 'Restore drill passed: archive is readable and schema/device/observation/job counts match.\n'
