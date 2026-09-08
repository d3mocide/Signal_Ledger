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

## Retention

Retention is never an unattended timer. An administrator first calls
`GET /v1/retention/preview`, reviews the exact candidate upload and run list,
then calls `POST /v1/retention/purge` with `{"confirm":"PURGE"}`. The sweep
expires source artifacts older than `RAW_RETENTION_DAYS` and removes complete
run evidence older than `NORMALIZED_RETENTION_DAYS`, including dependent
observations, affected baselines/findings, and devices no longer referenced by
any run. It records the action in the audit log.

Choose retention windows deliberately in `.env`; make a backup before any
sweep. The server does not schedule destructive work automatically.

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
