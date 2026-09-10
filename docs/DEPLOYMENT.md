# Production deployment runbook

Signal Ledger is intended to run behind a TLS-terminating reverse proxy. The
application container should not be exposed directly to an untrusted network.

## Before first use

1. Copy `.env.example` to `.env` and replace every placeholder with a secret
   generated outside the repository. Keep `HMAC_SECRET` separate from
   `APP_SECRET`, `ADDRESS_ENCRYPTION_KEY`, and `RAW_STORAGE_ENCRYPTION_KEY`.
   Set the raw-storage key if new upload artifacts should receive the optional
   application-level Fernet wrapping described in `POLICIES.md`.
2. Set `COOKIE_SECURE=true` when the browser reaches the app through HTTPS.
   Keep it `false` only for a local HTTP development instance.
3. Configure the proxy to forward only the application port, preserve the
   original HTTPS scheme, and redirect HTTP to HTTPS. Do not expose Postgres or
   Redis ports.
4. Run `docker compose up -d --build`, then verify `GET /health` and the
  `X-Content-Type-Options`, `X-Frame-Options`, and `Referrer-Policy` headers.
5. Create the first administrator through the browser and make a backup before
  importing source files.

The current UI includes Evidence Review, Rule Learning, Run Comparison,
privacy-safe device fingerprints, saved inventory views, and policy-bounded
device CSV export. These surfaces are authenticated and should be checked
against the intended role before granting access to another operator.

## Monitoring and logs

- Alert on a failed `/health` response, a restarting app container, a failed
  ingestion job, or a growing Redis queue.
- Review `docker compose logs --tail=200 app` after upgrades and imports. Logs
  must not be used to record raw addresses, HMAC secrets, passwords, upload
  contents, or encrypted address values.
- Review the in-app audit log for authentication, retention, key-change,
  category-override, baseline, disposition, and destructive-operation events.

`/health` verifies Postgres, Redis, and an RQ worker serving the
`signal-ledger` queue. It returns `200` only when all components respond,
otherwise `503` with a bounded component status map.
Application request, migration, health, and ingestion-completion events are
newline-delimited JSON written to the app container's standard output. These
events contain route/status/duration and bounded operational counts only; they
must not contain query values, capture contents, raw addresses, secrets,
passwords, cookies, raw storage paths, or upload names.

## Upgrade and rollback

1. Take and verify a database backup and separately snapshot the raw-upload
   volume if its retention window still requires the source files.
2. Record the image/repository revision being deployed.
3. Run `docker compose build app` and `docker compose up -d`; startup applies
   idempotent schema migrations before serving traffic.
4. Confirm the expected migration version is present in `schema_migrations`,
   then verify `/health`, sign in, review the overview, open one inventory
   record, and inspect the audit log. Run the backend suite from the rebuilt
   image.
5. If the application is unhealthy, stop writes, preserve logs, restore the
   known-good image, and use the guarded restore procedure in `OPERATIONS.md`.
   Never test a restore against the production database.

Automated build and API checks do not replace a browser acceptance pass. Before
calling a deployment production-ready, verify authenticated navigation,
responsive picker layouts, browser back/forward routes, evidence dispositions,
exports, and role restrictions in a real browser.

For the read-only stack checks after an upgrade, run:

```bash
scripts/verify_deployment.sh https://your-private-host.example
```

It verifies dependency-aware health, the browser security headers, and that
the migration ledger is populated. It does not replace the authenticated
browser checks above.
