# Signal Ledger — Current State

Status date: 2026-09-09

This document describes what is implemented in the current checkout. The
roadmap remains the source of truth for what is complete, pending, or still
needs production evidence.

## Product surface

Signal Ledger is a private, authorized-area discovery-log tool. The deployed
stack is:

```text
React/Vite UI + FastAPI API + RQ worker
        │
        ├── PostgreSQL/PostGIS
        └── Redis
```

The UI is served by FastAPI from the app container. Imports are queued through
Redis and processed by the RQ worker under Supervisor.

## Implemented workflows

### Collection and ingestion

- First-run administrator setup, login, four bounded roles, and server-side
  opaque HttpOnly sessions.
- Authorized collections and capture runs with authorization references,
  precision policy, optional polygon boundaries, and coverage estimates.
- WiGLE CSV and Kismet CSV/JSON/NDJSON-shaped parser contracts with bounded
  validation reports, duplicate handling, source hashes, and import history.
- Human-readable import reports and explicit run completion.
- Retention preview/purge, audit logging, and administrative session controls.

### Inventory and evidence

- Pseudonymous device inventory with server-side filters, pagination, sorting,
  category and role filters, OUI evidence, and first/last-seen context.
- Device evidence view with retained source facts, coarse-cell counts, audited
  category override, and policy-gated exact-address reveal for administrators.
- Local OUI enrichment. Locally administered/randomized addresses remain
  unattributable.
- Coarse-cell coverage and analytics views; geographic basemap mode is explicit
  opt-in when configured.

### Categorization and review

- Category rule set `rules-v6` uses OUI organization, device name/type, SSID,
  protocol, and address scope.
- Orthogonal role rule set `roles-v1` currently covers `retail_pos`,
  `security_access`, `smart_home`, `industrial_ot`, `medical`, and
  `guest_network`.
- Evidence review groups repeated signals and supports pagination, optional
  analyst context, status dispositions, insufficient-evidence handling, and
  single-device category overrides.
- Rule Learning records category corrections as versioned proposals. Proposal
  acceptance is audited and never automatically promotes a production rule.
- Learning summary supports collection/time-window review counts, override
  counts, and a dismissed-among-confirmed/dismissed false-positive signal.

### Comparison, similarity, and export

- Privacy-safe device fingerprints use vendor, protocol, type, normalized name
  signals, security, activity windows, and coarse cells. Results expose an
  opaque HMAC-derived fingerprint and shared signal families, not raw
  addresses or identity merges.
- Run Comparison reports new, returning, changed, and disappeared devices
  between two runs in the same collection.
- Inventory saved views preserve area, vendor, category, role, attribution,
  sorting, and direction filters.
- Device CSV exports contain pseudonymous tokens, categories, confidence,
  roles, and provenance fields. Raw addresses, HMAC secrets, and exact
  coordinates are excluded.

## Navigation and URLs

The SPA uses hash routes so the server can continue serving one private app
entry point without a separate history-fallback proxy configuration. Examples:

```text
/#overview
/#inventory
/#reviews
/#learning
/#comparison
/#device?id=123
```

Navigation buttons create browser history entries. Browser back/forward
restores recognized page routes, and device deep links restore the selected
device. Evidence-review pagination is bounded server-side; its current filter
state is component-local rather than encoded in the URL.

## Data and privacy boundaries

- Full device addresses are not stored in normalized tables by default.
- Device tokens are site-scoped HMAC pseudonyms and are not cross-site
  identity claims.
- Exact-precision addresses are encrypted and revealable only by an admin;
  every reveal is audited.
- Category, role, fingerprint, comparison, and baseline outputs are review
  aids, not person identification, ownership claims, or security verdicts.
- Exports are policy-bounded and never include raw addresses, secrets, or exact
  coordinates by default.

## Schema and validation

The project uses the custom idempotent migration runner in
`app/migrations.py`, not Prisma or automatic ORM migrations. The live schema
currently includes migration `0013_rule_proposals`.

Current evidence:

- 47 containerized backend tests pass.
- Frontend TypeScript/Vite production build passes.
- Live `/health` check passes after deployment.
- `git diff --check` passes for the current worktree.

The visual browser acceptance pass remains open because automated build and API
success do not prove keyboard, responsive, or authenticated browser behavior.

## Remaining work

See [`ROADMAP.md`](ROADMAP.md) for the authoritative checklist. The immediate
gates are end-to-end upload-to-finding integration tests, realistic load tests,
backup/restore and HMAC-rotation drills, accessibility/responsive/browser
validation, categorization threshold tuning from representative feedback, and
deployment monitoring/upgrade evidence.
