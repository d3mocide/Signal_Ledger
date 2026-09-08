# Signal Ledger

Private, authorized-area discovery-log observatory. It ingests the explicitly tested Phase 1 WiGLE CSV and Kismet CSV/NDJSON-shaped exports, derives site-scoped device tokens, attributes only globally administered OUI prefixes, and provides an operator-facing inventory, coarse-cell coverage, and basic discovery analytics.

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

The UI supports first-run administrator creation, login, administrator-managed user roles, authorization references, survey areas/runs, asynchronous upload jobs, idempotent source hashes, validation reports, audit events, pseudonymous inventory, and coarse spatial cells. It rejects malformed MAC addresses and avoids OUI attribution for locally administered addresses. PostGIS is available in the database, but current batch ingestion uses stored coordinates and coarse cells rather than populated geometry fields.

Run parser tests with python -m pytest after installing requirements, or inside the app image with docker compose exec app pytest.

This remains a private-tool foundation, not yet a production security deployment: reviewed full IEEE OUI import, malware scanning, signed upload URLs, retention deletion, precise-area polygon enforcement, backup/restore drills, and the explainable anomaly evaluator remain later slices.
