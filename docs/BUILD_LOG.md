# Signal Ledger — Build Log

This is an append-only engineering log. It records what changed, the evidence
we have, and what that evidence does **not** prove. Product intent belongs in
`plan.md`; decisions belong in `DESIGN.md`; remaining work belongs in
`ROADMAP.md`.

## 2026-09-07 — Initial vertical slice and first field import

### Built

- Created the minimal Compose stack: one app container (React/Vite build,
  FastAPI API, and RQ worker under Supervisor), PostgreSQL/PostGIS, and Redis.
- Replaced the first static UI with a React/TypeScript client and served its
  Vite assets correctly from FastAPI.
- Added first-run administrator setup, Argon2 passwords, opaque persistent
  HttpOnly sessions, login/logout, and administrator-managed roles.
- Added areas, survey runs, asynchronous uploads, job status/report APIs,
  HMAC-pseudonymous devices, offline seed OUI lookup, inventory, and coarse
  coverage/analytics views.
- Added WiGLE and Kismet-shaped parser fixtures, including WiGLE 1.6 metadata
  before the actual CSV header.

### Evidence

- Parser/security test suite: **6 passed**.
- The Compose stack reached healthy app/database/queue service state.
- An authorized real WiGLE CSV import completed with parser version
  `phase1.2`: **26,705 accepted**, **0 rejected**, **3 duplicates skipped**;
  the resulting import report stated **90% collector coverage**.
- The imported run produced **25,498 distinct pseudonymous devices** in the
  worker’s aggregate report.

### Corrections made during the slice

- Fixed static Vite asset routing that served JavaScript with a JSON MIME type.
- Fixed first-run form behavior so setup actually submits and establishes the
  session.
- Added parsing support for the WiGLE 1.6 metadata/header arrangement.
- Changed ingestion from per-record database work to batched writes so a
  real-world upload can finish in a reasonable time.
- Removed raw storage path and file hash from job response views.

### Still unproven / not yet done

- No browser-driven acceptance pass has yet confirmed every React flow after
  the latest UI rebuild.
- No production security, backup/restore, at-rest encryption, malware scan,
  retention deletion, or full OUI-data validation has been performed.
- Current coverage uses latitude/longitude-derived coarse cells. Although the
  database has PostGIS support, batch ingestion does not currently populate a
  geometry field; documentation must not claim that it does.
- The map is currently a coverage-density view, not the planned interactive
  MapLibre map. Baselines, anomaly workflows, and device-detail evidence are
  still future work.

## 2026-09-07 — Local coarse session mapping

### Built

- Added a local SVG map of coarse observation cells, filterable by area, run,
  and a selected pseudonymous device.
- Extended the map aggregate endpoint with bounded `run_id` and `device_id`
  filters plus device counts per cell.

### Boundary

- This is a geographic plotting surface, not a road/imagery basemap. It keeps
  the existing coarse-cell policy and makes no requests to a map-tile provider.
- A selected device shows only the rounded cells in which its observations
  occurred. It does not claim the device’s exact location or a continuous path.

## Entry template

```md
## YYYY-MM-DD — short milestone

### Built
- ...

### Evidence
- Command/test/manual check and result.

### Still unproven / follow-up
- ...
```
