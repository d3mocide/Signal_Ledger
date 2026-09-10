#!/usr/bin/env bash
set -euo pipefail

# Destructive: replaces the configured database with the supplied pg_dump archive.
archive="${1:?Usage: scripts/restore.sh path/to/signal-ledger.dump}"
if [[ ! -f "$archive" ]]; then
  printf 'Backup not found: %s\n' "$archive" >&2
  exit 2
fi
if [[ "${CONFIRM_RESTORE:-}" != "YES" ]]; then
  printf 'Refusing restore. Re-run with CONFIRM_RESTORE=YES after making a fresh backup.\n' >&2
  exit 2
fi

if [[ -f "$archive.sha256" ]]; then
  sha256sum --check "$archive.sha256"
fi
docker compose exec -T db sh -lc 'pg_restore --list >/dev/null' < "$archive"

docker compose exec -T db sh -lc 'dropdb -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
docker compose exec -T db sh -lc 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --exit-on-error' < "$archive"
printf 'Restore completed. Restart the app container to re-run schema setup.\n'
