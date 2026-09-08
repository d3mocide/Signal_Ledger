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
- No production security, backup/restore drill, at-rest encryption, malware
  scan, automated retention, or full OUI-data validation has been performed.
- Current coverage uses latitude/longitude-derived coarse cells. New ingestions
  also populate the PostGIS geometry field, but the UI does not expose precise
  points.
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

## 2026-09-08 — Phase 1 explorer evidence pass

### Built

- Made import history selectable and exposed each job’s parser/source/report
  facts, including rejection reasons when present.
- Added paginated inventory totals and a device-evidence page with retained
  source facts, observation/run/cell counts, and a direct map-sightings action.
- Added explicit run completion from the survey workspace.
- Added a database-backed explorer contract test for inventory pagination,
  device evidence, and run/device coarse-map filtering.

### Still unproven

- This validates the backend contract and production frontend build, not a
  browser-driven acceptance pass over the newly added UI paths.

## 2026-09-08 — Phase 1 query and report completion slice

### Built

- Unified bounded area/run/device/time/protocol/vendor/category/RSSI/quality
  filters across the discovery APIs.
- Replaced Python-side analytics aggregation with grouped database queries for
  protocol, category, vendor, daily observations, and mean quality.
- Added a coarse-map filter bar and a human-readable downloadable import report.
- New ingestions now report location completeness and populate the existing
  PostGIS geometry column while the UI remains coarse-cell by default.

### Boundary

- Existing imports retain their original reports and are not retroactively
  assigned location-completeness metadata.
- Geometry is stored for approved future spatial queries; it is not exposed as
  precise points by the current UI.

## 2026-09-08 — Native Kismet log support

### Evidence and implementation

- Inspected two authorized Kismet 2025.09 schema-v9 SQLite logs: one empty
  capture and one 5.9 MB capture with 243 device summaries, all with averaged
  GPS locations.
- Added a read-only `.kismet` adapter that uses only the `devices` summary
  table. It does not query `packets`, `data`, alerts, or JSON/blob columns.
- Added a generated SQLite parser fixture that proves packet-table data is not
  read. The suite passed 8/8 after the change.

## 2026-09-08 — Baseline and finding workflow

### Built

- Added frozen baselines from completed area runs. Each captures its training
  runs, known pseudonymous devices, valid OUI organizations, coarse footprints,
  time windows, Wi-Fi profiles, and coverage mean.
- Added explainable later-run findings for novel device/vendor, spatial and
  temporal outliers, Wi-Fi profile changes, and low-coverage runs.
- Added analyst-review UI to create/evaluate baselines and confirm, dismiss, or
  flag findings for review. Baseline/evaluation/disposition actions are audited.
- Added an admin run-deletion API; later retention coverage tests exercise the
  shared transaction path.
- Added a baseline novelty rule test; the suite passed 9/9.

### Boundary

- Findings are triage prompts with explicit score/confidence, not automated
  security conclusions. They require representative, completed training runs.

## 2026-09-08 — Versioned IEEE OUI enrichment

### Built

- Validated the official IEEE MA-L CSV shape (40,108 entries at validation).
- Added a locally stored, versioned OUI-import catalog and administrator CSV
  upload control. Only six-hex-digit prefix and organization name are retained.
- Existing pseudonymous devices are re-enriched when a new catalog is loaded;
  locally administered/random addresses remain unattributable.
- Added an importer/re-enrichment test; the suite passed 10/10.

## 2026-09-08 — Operational retention and recovery controls

### Built

- Added an administrator-only retention preview plus a separately confirmed
  purge action. It expires old raw uploads and removes expired run evidence,
  dependent findings/baselines, and unreferenced device tokens in one database
  transaction; raw files are unlinked only after the transaction commits.
- Added configurable raw and normalized retention windows, audited sweep
  records, account disable/session-revocation controls, response hardening, and
  Redis-backed request limiting.
- Added guarded database backup/restore scripts and an operations runbook with
  a non-destructive HMAC rotation/re-baselining procedure.
- Added a retention contract test. The suite now covers 11 tests.

### Boundary

- Retention is explicitly administrator-triggered; it is not an unattended
  deletion timer. Backup restores and HMAC rotation have procedures but still
  require a disposable-stack drill before a production claim.

## 2026-09-08 — Direct captures and interpretable map context

### Built

- Reframed the UI around direct capture imports: a WiGLE/Kismet file now creates
  a completed session from its filename and import time under `Personal
  captures`. Collections and manually named sessions remain optional grouping,
  rather than required setup.
- Rejected placeholder `0,0` and out-of-range GPS fixes for new imports, and
  excluded legacy placeholder points from map queries.
- Added a coarse, segmented collection track to the map. It is based on the
  receiver's rounded GPS cells, breaks across sessions and five-minute gaps,
  and is explicitly separate from device sightings.

### Evidence

- Added direct-import and placeholder-GPS/track regression coverage; the suite
  passed 14 tests after the changes.

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

## 2026-09-08 — Frontend command-center redesign

- Replaced the introductory landing-page layout with persistent grouped navigation,
  a workspace header, compact page titles, refresh/import actions, and a responsive
  charcoal/lime visual system. All existing exploration and management workflows
  remain available; existing uncommitted backend changes were preserved.
- Added an operational overview driven by the existing APIs: retained observation
  and device counts, survey status, coarse spatial footprint, protocol composition,
  last 28 observed collection days, open/needs-review findings, and selectable import
  validation summaries. Charts describe retained evidence rather than live radio activity.
- Restyled inventory, coarse maps, source evidence, surveys, baselines, review,
  administration, and authentication. Added keyboard focus styling, a skip link,
  field labels, horizontal table scrolling, responsive navigation, and request-error
  notifications. Fixed async form reset targets and import-polling timeout feedback.
- Validation: TypeScript and Vite production build pass; git diff whitespace check
  passes. Compiled frontend assets copied to the running local app without restarting
  its backend. Browser provider was unavailable, so visual layout, keyboard traversal,
  and authenticated end-to-end interaction still require browser verification.

## 2026-09-08 — Geographic basemap privacy gate

### Built

- Added an explicit privacy decision for the optional MapLibre geographic
  basemap: switching on "Show geographic basemap" now surfaces a dismissible
  notice naming the tile provider each time it is enabled, and the capture-map
  explainer text is state-dependent so it no longer claims "no third-party map
  tiles" while the basemap is active.
- Switched the basemap tile source from raw `tile.openstreetmap.org` raster
  tiles to CARTO's vector GL style (`dark-matter-gl-style`), since the raw OSM
  endpoint is not licensed for embedding in a third-party application and
  actively 403s requests without a permitted Referer. CARTO's basemap service
  is built for exactly this and is free under a fair-use monthly tile-request
  limit.
- Added a server-held `CARTO_API_KEY` (`.env`, blank by default) surfaced to
  the frontend only through the authenticated `/v1/me` response as
  `map_tile_key`, so the key is never baked into the built JS bundle and stays
  configurable without an image rebuild once the container restarts. The
  toggle button is disabled with an explanatory title until an administrator
  sets the key.

### Boundary

- The local coarse-grid map remains the default view; the notice is
  per-activation (dismissing it does not suppress it the next time the
  basemap is turned on), not a one-time or persisted consent record.
- A `CARTO_API_KEY` was provisioned in this local environment's `.env` and the
  basemap was confirmed rendering CARTO's dark-matter tiles with the capture
  track/points overlaid, in the running app after a container rebuild.

### Still unproven / follow-up

- Verified in this local browser session; no automated browser test covers it.

## 2026-09-08 — Dashboard map legibility and IEEE OUI auto-fetch

### Built

- Fixed a rendering bug where an extreme corner data point's halo (up to 31px
  radius) could bleed past the local coarse-grid map's plot rectangle and
  visually cover the axis tick labels. `LocalMap`'s coordinate mapping now
  insets the plottable area by the maximum halo radius on every side.
- Gave the dashboard's compact "Observation footprint" card its own wider
  internal plot layout (1120x300 viewBox instead of reusing the full page's
  800x464), and switched the card's CSS from a fixed height to an
  `aspect-ratio` matching that viewBox exactly. Previously the card forced a
  height that didn't match the map's native aspect ratio, so excess width was
  padded with letterbox bars that were only invisible because their color
  happened to be nearly identical to the map's own background — the fix
  removes that wasted, accidentally-hidden space instead of only papering
  over it.
- Added an admin-triggered "Refresh from IEEE" action (`POST /v1/oui/refresh`)
  that fetches the official `oui.csv` registry directly from
  standards-oui.ieee.org over HTTPS on the server and runs it through the
  existing versioned `OUIImport`/`OUIAssignment` pipeline, so an administrator
  no longer has to manually download and re-upload the CSV. It shares
  validation, hashing, idempotency, and re-enrichment logic with the manual
  upload path via a common `apply_oui_csv` helper, and records a distinct
  `oui.refreshed` audit action so provenance (manual upload vs. server fetch)
  stays visible in the audit trail. No API key or third-party intermediary is
  involved; IEEE is the same authoritative source the manual upload already
  trusted.

### Boundary

- The IEEE auto-fetch remains a deliberate, admin-triggered action (a button
  click), not a background/scheduled job — consistent with how retention and
  HMAC rotation are handled elsewhere in this project.
- Only the MA-L registry (`oui.csv`) is fetched, matching the existing
  importer's 24-bit-prefix-only scope; MA-M/MA-S are still out of scope.

### Evidence

- Added `test_oui_refresh_fetches_and_applies_the_ieee_registry` (including
  its idempotent-repeat path) and
  `test_oui_refresh_surfaces_a_clear_error_when_ieee_is_unreachable`, both
  exercising `refresh_oui` with `urllib.request.urlopen` mocked so the suite
  makes no real network call. The suite passed 16/16 after the change.

## 2026-09-08 — Device inventory sort, filter, and last-seen network facts

### Investigated

- With this environment's real 25,498-device, 40,109-assignment IEEE MA-L
  catalog, ~12,766 devices have no OUI prefix at all: `tasks.py` deliberately
  sets `oui_prefix = None` when the address's locally-administered bit is set,
  since a randomized MAC's "manufacturer" is not a meaningful fact. Of the
  remainder, ~4,100 carry a real registered prefix that still isn't in the
  MA-L file — almost certainly MA-M/MA-S (28-/36-bit) assignments, which the
  importer intentionally excludes (see the 2026-09-08 IEEE OUI enrichment
  entry). Device `category` is "unknown" for 100% of devices in this
  environment because the category-rule engine is still an open roadmap item,
  not because classification is failing.

### Built

- `/v1/devices` now accepts `attributed_only` (excludes `oui_organization =
  "unattributable"`) and `sort`/`direction` over an explicit allow-list
  (`last_seen`, `first_seen`, `oui_organization`, `category`), replacing the
  previous hardcoded `last_seen desc` order.
- Each returned device now carries `last_protocol` and `last_ssid`, taken from
  its own most-recently-captured observation (one bounded follow-up query per
  page, keyed off the already-paginated device ids — not a per-table scan).
  This surfaces the network name/radio type context that previously required
  opening every device's evidence page individually.
- The inventory table gained sortable "OUI organization"/"Category"/"First
  seen"/"Last seen" column headers, an "Attributed only" checkbox, and new
  "Radio"/"Last network" columns.

### Boundary

- The pseudonymous site-scoped token remains the only device identifier
  exposed; raw MAC/BSSID is still never surfaced anywhere in the UI or API,
  per the existing privacy design. `last_ssid` is the network name observed,
  not a device address.
- The category column/sort is wired up for when the classification engine
  ships, but is not yet useful on its own since every device is "unknown"
  today.

### Evidence

- Extended `test_inventory_detail_and_coarse_map_filters_work_together` to
  assert `last_ssid`/`last_protocol` reflect the most recent observation
  (not just the first), that `attributed_only` excludes the unattributable
  device, and that `sort=oui_organization` returns vendor-ascending order.
  The suite passed 16/16 after the change.

## 2026-09-08 — Privileged address reveal, collection management, vendor ledger

### Built

- **Optional, audited real-address retention.** Added `Device.encrypted_address`
  (nullable, migration `0004_device_encrypted_address`) and `app/crypto.py`
  (Fernet, via the new `cryptography` dependency). `process_ingestion` now
  encrypts and stores a device's real MAC/BSSID *only* the first time it is
  observed in a survey area whose `precision` is `"exact"`; areas left at the
  default `"coarse"` behave exactly as before and never retain it. Nothing is
  stored unless `ADDRESS_ENCRYPTION_KEY` is set in `.env` (blank by default,
  same "inert until configured" pattern as `CARTO_API_KEY`). A new admin-only,
  audited `POST /v1/devices/{id}/reveal-address` decrypts it on demand; the
  Device Evidence page shows a "Reveal address" action, visible only to the
  admin role, only when the device has a stored address. `dump(Device)`
  responses never include the raw encrypted column — a `device_view()` helper
  strips it to a `has_stored_address` boolean before anything leaves the API.
- **Collection (survey area) management.** Creation already existed on the
  Surveys page; added `PATCH /v1/survey-areas/{id}` (admin-only, audited
  rename) and enriched `GET /v1/survey-areas` with each area's run/device
  counts. Added a "Collections" panel to Administration listing every area
  with those counts and a rename control.
- **Vendor breakdown ("ledger") page.** Added `GET /v1/devices/vendors`
  (optionally `area_id`-scoped) returning every OUI organization ranked by
  device count with its share of the total. New "Vendor breakdown" nav page
  reuses the existing `.bar`/`.coverage` chart component (same visual language
  as the Coverage page's cell-count bars — single accent hue, no new
  categorical palette needed since it's one ranked measure, not multiple
  simultaneous series) for the top 15 vendors, plus a full sortable table.
  Clicking a vendor jumps to Inventory pre-filtered to it.

### Boundary

- Re-filing an already-imported run into a different collection afterward
  (the existing "File into collection" action) does not retroactively change
  address retention for observations already processed — only future
  ingestions honor the run's collection precision at the time of processing.
  This is a hard boundary: a coarse-area device's real address is never
  recoverable after the fact, by design (matches "old data can't be
  un-hashed").
- Collection rename is the only management action shipped; deleting a
  collection was deliberately deferred — it has retention/data-loss
  implications that overlap the existing run-level retention/purge system and
  deserve their own decision rather than being bundled in here.
- `ADDRESS_ENCRYPTION_KEY` rotation has no procedure yet, unlike the existing
  HMAC-key rotation drill; a key rotation would orphan any already-encrypted
  addresses under the old key.

### Evidence

- `process_ingestion` had never been exercised directly by the test suite
  (only through the RQ-enqueuing HTTP endpoints) because its PostGIS geometry
  backfill has no sqlite equivalent; testing the new encryption behavior
  required calling it directly, so a `_PostgisAgnosticSession` test helper
  stubs out only that one statement. This surfaced a real bug the same
  refactor introduced (a stale 4-tuple unpack in the `located` count) that no
  existing test would have caught before deployment.
- Added tests for: exact-vs-coarse address retention and reveal (including the
  409 paths for "no stored address" and an unconfigured key), collection
  listing/counts/rename (plus the empty-name 422), and vendor-summary ranking
  with area scoping. The suite passed 20/20 after the change.

## 2026-09-08 — Retention label layout fix and bulk session filing

### Built

- Fixed the retention panel's "Type PURGE to run the reviewed sweep" label:
  it was a bare `<label>` instead of using the `field-label` class every other
  labeled input in the app uses, so it fell back to inline layout and visually
  collided with the input's focus ring instead of stacking above it.
- Recent captures on the Surveys page can now be filed into a collection as a
  batch: each row got a checkbox (plus a "select all" for the visible list),
  and one shared control above the list picks an existing collection or names
  a new one and applies it to every checked session in one action. This
  replaces the previous one-row-at-a-time free-text form. No backend change
  was needed — it fans out to the existing per-session
  `POST /v1/sessions/{id}/collection` endpoint.

### Boundary

- The bulk action only covers the first 20 visible recent-capture rows,
  matching the existing list's display cap.

## 2026-09-08 — Command-center metric cards updated for the direct-capture model

### Built

- Replaced two dashboard metric cards that still reflected the earlier
  required-survey-area model: "Survey runs" is now "Capture sessions" (using
  the already-computed `completed_runs` from `/v1/overview` instead of
  recomputing it client-side), and "Authorized areas / Defined collection
  boundaries" — which no longer matches a workflow where collections are
  optional labels, not a required authorization boundary — is now "Attributed
  devices", showing the OUI-attribution rate and unattributable count
  (`/v1/overview` already computed `unattributable`; it just wasn't exposed to
  the frontend `Overview` type or used yet).

## 2026-09-08 — Fixed unreachable collection-creation UI on the Surveys page

### Found

- The `Surveys` component had two `return` statements. The first (the
  "capture-flow" quick-upload and recent-captures list) executed and returned
  immediately, making everything after it — the "Collection" creation form
  (the *only* place to create a collection with `precision: "exact"`), the
  "Named session" form, the third direct-import form, and the `addArea`,
  `addRun`, `complete`, and `upload` handlers — permanently dead code. It
  never rendered, in any state, for any user. This is why there was no way to
  create a collection at all, exact or otherwise, only to file an existing
  session into one (or implicitly create a coarse one by typing a new name
  while filing) — and it means the exact-precision-area workflow documented
  earlier today was never actually reachable through the UI.
- TypeScript's compiler did not catch this because both branches were
  individually valid, reachable-looking JSX; nothing here is a type error,
  only a control-flow dead end.

### Fixed

- Merged both returns into one (a fragment containing both the capture-flow
  panel and the previously-dead cards panel), and moved the four now-shared
  handler functions above it. No behavior was removed — every previously-dead
  form and list is now live, alongside today's bulk-file and dashboard changes.

### Boundary

- This was caught by the user testing the exact-precision workflow live in
  the browser, not by the test suite or type-checking — neither would have
  caught it, since it's a rendering/control-flow defect, not a type or logic
  error. No automated regression test was added for "the intended UI actually
  renders"; that class of bug needs a browser-driven check, which remains an
  open item (see the Phase 1 "browser-driven acceptance pass" boundary noted
  throughout this log).
