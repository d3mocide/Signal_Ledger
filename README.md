# Signal Ledger

Private, authorized-area discovery-log observatory. It ingests WiGLE CSV and Kismet CSV/NDJSON/native-summary exports, derives site-scoped device tokens, attributes only globally administered OUI prefixes, and provides an operator-facing inventory, coarse-cell coverage, and reviewable baseline findings.

## Run it

1. Copy .env.example to .env and replace every secret/password.
2. Run docker compose up --build.
3. Visit http://localhost:8000.

The stack intentionally uses three containers: app (FastAPI, static UI, and RQ worker under a supervisor), db (PostgreSQL/PostGIS), and redis (durable job queue). Raw uploads live on a named app volume; production encryption-at-rest should be supplied by the host volume or storage platform. On first use, create the initial administrator account in the UI. Passwords are Argon2-hashed and sessions are opaque HttpOnly cookies.

## Project records

- [Product & technical plan](plan.md) — original requirements and scope.
- [Design brief](docs/DESIGN.md) — current decisions, boundaries, and system shape.
- [Delivery roadmap](docs/ROADMAP.md) — every phase, checked honestly against evidence.
- [Build log](docs/BUILD_LOG.md) — append-only implementation and validation history.

## Current MVP boundary

The UI supports first-run administrator creation, login, administrator-managed user roles, authorization references, survey areas/runs, asynchronous upload jobs, idempotent source hashes, validation reports, audit events, pseudonymous inventory, coarse spatial cells, versioned local OUI enrichment, and non-automated baseline findings. It rejects malformed MAC addresses and avoids OUI attribution for locally administered addresses. New ingestion batches populate PostGIS geometry while the UI deliberately presents only coarse cells.

Run parser tests with python -m pytest after installing requirements, or inside the app image with docker compose exec app pytest.

## Operational defaults

The included defaults retain raw uploads for 30 days and normalized observations
for 365 days; set them explicitly in `.env` before a real deployment. The app
uses opaque HttpOnly sessions, Redis-backed request limits, security response
headers, and administrator session-revocation controls. Set `COOKIE_SECURE=true`
behind HTTPS.

This remains a private-tool foundation, not yet a production security deployment:
malware scanning, signed upload URLs, precise-area polygon enforcement,
backup/restore and HMAC-rotation drills, load testing, and accessibility
validation remain operational hardening work. See [the operations runbook](docs/OPERATIONS.md)
before using retention, backup, restore, or key rotation.
