#!/usr/bin/env bash
set -euo pipefail

# Read-only post-upgrade verification for a local or proxied Signal Ledger app.
base_url="${1:-http://localhost:8000}"
health="$(curl --fail --silent --show-error "$base_url/health")"
if [[ "$health" != *'"status":"ok"'* || "$health" != *'"database":true'* || "$health" != *'"redis":true'* || "$health" != *'"worker":true'* ]]; then
  printf 'Deployment verification failed: health dependencies are not all ready.\n' >&2
  exit 1
fi

headers="$(curl --fail --silent --show-error --dump-header - --output /dev/null "$base_url/")"
for expected in 'X-Content-Type-Options: nosniff' 'X-Frame-Options: DENY' 'Referrer-Policy: same-origin'; do
  if ! grep -qiF "$expected" <<< "$headers"; then
    printf 'Deployment verification failed: missing response header %s\n' "$expected" >&2
    exit 1
  fi
done

migration_count="$(docker compose exec -T db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "SELECT count(*) FROM schema_migrations"')"
if [[ ! "$migration_count" =~ ^[1-9][0-9]*$ ]]; then
  printf 'Deployment verification failed: no schema migrations recorded.\n' >&2
  exit 1
fi
printf 'Deployment verification passed: health dependencies, response headers, and %s schema migrations are ready.\n' "$migration_count"
