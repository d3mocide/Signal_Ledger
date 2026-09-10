#!/usr/bin/env bash
set -euo pipefail

# Create a portable, compressed PostgreSQL backup. Run from the repository root.
# The database remains online; this does not include files in the raw-upload volume.
backup_dir="${1:-./backups}"
mkdir -p "$backup_dir"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="$backup_dir/signal-ledger-$stamp.dump"

docker compose exec -T db sh -lc 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$target"
docker compose exec -T db sh -lc 'pg_restore --list >/dev/null' < "$target"
sha256sum "$target" > "$target.sha256"
printf 'Created and verified %s\n' "$target"
printf 'Checksum %s.sha256\n' "$target"
