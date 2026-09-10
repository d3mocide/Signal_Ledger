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
`0013_rule_proposals`.
