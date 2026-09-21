# Operations runbook

## Backups and restore

From the repository root, create a portable PostgreSQL backup with:

```bash
scripts/backup.sh
```

The archive is placed in `./backups/` by default. Raw upload artifacts live in
the application volume and are intentionally not bundled into a database dump;
copy that volume separately if source-file retention is required.

Restore is intentionally guarded because it replaces the running database.
First make and verify a new backup, stop writers, then run:

```bash
CONFIRM_RESTORE=YES scripts/restore.sh backups/signal-ledger-YYYYMMDDTHHMMSSZ.dump
docker compose restart app
```

Verify the restored state by signing in, reviewing the overview count, opening
one inventory record, and checking the audit log. Do not test restores against
the production database.

Run a non-destructive restore drill regularly from the repository root:

```bash
scripts/backup_restore_drill.sh
```

It backs up the active database, restores it to a temporary database in the
same Postgres container, compares migration/device/observation/job counts, and
then removes the temporary database and archive. It never replaces the active
application database.

## Retention

Retention is never an unattended timer. An administrator first calls
`GET /v1/retention/preview`, reviews the exact candidate upload and run list,
then calls `POST /v1/retention/purge` with `{"confirm":"PURGE"}`. The sweep
expires source artifacts older than `RAW_RETENTION_DAYS` and removes complete
run evidence older than `NORMALIZED_RETENTION_DAYS`, including dependent
observations, affected baselines/findings, and devices no longer referenced by
any run. It records the action in the audit log.

Choose retention windows deliberately in the administrator retention control;
the initial defaults may be supplied through `.env` before the first settings
row is created. Make a backup before any sweep. The server does not schedule
destructive work automatically.

## Upload scanning

The application rejects unsupported extensions, source/format mismatches,
invalid UTF-8/control bytes, malformed JSON, and CSV captures without a
recognizable MAC/BSSID header before it creates a job or sends anything to a
parser. It can also execute a local scanner command without a shell.

Set `UPLOAD_SCANNER_COMMAND` to the exact scanner invocation available in the
app container. The command receives the unmodified upload on standard input,
must emit no sensitive capture content to the application logs, and must exit
zero only when the artifact is clean. Set `UPLOAD_SCANNER_REQUIRED=true` in a
deployment that must reject uploads when the command is not configured, cannot
start, times out, or reports a nonzero result. `UPLOAD_SCANNER_TIMEOUT_SECONDS`
defaults to 120 and is bounded to 1–600 seconds.

Qualify the selected scanner and its definitions in the deployment environment
with an authorized harmless test fixture and a known-detection fixture. Record
the image revision, scanner version/definition revision, command, result, and
timestamp outside this repository. This hook does not itself isolate parsing;
use and qualify the optional parser-isolation profile for shared deployments.

## Optional parser isolation

The default private installation parses in the RQ worker. A hardened deployment
can instead enable an additional `parser` profile which receives a bounded
capture stream over a Unix socket and returns normalized records to that worker.
The parser has no network, no database/Redis credentials, no raw-upload volume,
a read-only root filesystem, dropped Linux capabilities, a `noexec` temporary
filesystem, 64 process IDs, 0.5 CPU, and a 768 MiB container memory cap. It is
not started by the normal three-service Compose command.

Enable it only after the host can reserve its resource limits:

```bash
PARSER_ISOLATION_MODE=required docker compose --profile parser-isolation up -d --build
```

Wait for `docker compose --profile parser-isolation ps` to show the parser as
healthy before submitting a capture. This avoids an intentional fail-closed
rejection during its short socket-startup window.

The application rejects a new upload before it creates a job when the
Unix-socket service is unavailable; it also fails the ingestion closed if the
service does not complete within `PARSER_ISOLATION_TIMEOUT_SECONDS` (default
120 seconds). The parser itself limits virtual memory to 512 MiB,
CPU time to 90 seconds, and input size to the application's 100 MiB maximum;
the `.env` values can lower or raise the first two within bounded ranges. Each
ingestion report identifies `parser_isolation` as `isolated` or `in_process`.
In required mode, `/health` also reports the parser as a required dependency.

Validate this profile with representative authorized WiGLE and native Kismet
fixtures, an intentional parser-service outage, and a capture near the 100 MiB
limit. Keep it enabled for shared or third-party capture intake; personal,
local-only deployments may deliberately leave it off.

## HMAC pseudonym rotation

The HMAC secret scopes every device token. Rotating it changes all device
identifiers and invalidates comparisons to existing baselines. There is no
safe in-place token rewrite.

1. Take and verify a backup.
2. Record the current secret version and the intended cutover date outside the
   application repository.
3. Stop ingestion, set a new random `HMAC_SECRET` in the deployment secret
   store, and restart the app and worker.
4. Start a new authorized survey/baseline epoch. Re-import only source files
   whose retention and authorization permits reprocessing; otherwise retain
   prior aggregate reports only.
5. Verify new inventory tokens differ and document the discontinuity in the
   audit/change record.

Never put an HMAC secret in source control, exports, screenshots, or audit
details.

The regression suite re-ingests the same authorized fixture under two
disposable secrets and verifies that it creates two distinct token epochs.
Run it only with the rest of the containerized suite; it does not change the
configured deployment secret.

## Load drill

Use a separate Compose project and remove its volumes afterward. The supplied
script generates synthetic data only and refuses to run without its explicit
environment guard:

```bash
docker compose -p signal-ledger-load up -d db redis
docker compose -p signal-ledger-load run --rm -e SIGNAL_LEDGER_LOAD_TEST=YES \
  -v "$PWD/scripts:/scripts:ro" app python /scripts/load_test.py --rows 5000
docker compose -p signal-ledger-load down -v
```

Record the JSON timing result with the host and image revision. The drill
checks worker-style import completion and inventory/map explorer queries at
the same volume; it is a capacity baseline, not a production SLA.

## Review learning and exports

Use the Evidence Review page to inspect grouped uncertain classifications. Notes
and evidence references are optional handoff context; dispositions and category
overrides are the durable audited actions. A single-device category override
also creates a versioned proposal in Rule Learning. Accepting a proposal marks
it as reviewed but does not alter the live categorization rules automatically.

Rule Learning can be filtered by collection and review time window to measure
dispositions, overrides, and dismissed-among-confirmed/dismissed signals. Treat
that rate as analyst feedback, not as an unattended threshold-tuning command.

Run Comparison is limited to two runs from the same collection and reports
new, returning, changed, and disappeared pseudonymous devices. Device
fingerprints are bounded similarity suggestions, not identity merges.

Inventory CSV exports are policy-bounded. Review the selected filters before
exporting, and handle the resulting pseudonymous tokens as sensitive workspace
data even though raw addresses and secrets are excluded.

## Schema migrations

Schema changes use the idempotent migration runner in `app/migrations.py`.
There is no Prisma schema or automatic ORM migration generation. App startup
applies unapplied versions recorded in `schema_migrations`. During an upgrade,
confirm the new version is recorded and run the rebuilt-image test suite before
accepting traffic. The current feature set includes migration
`0015_category_rules_v7`.
