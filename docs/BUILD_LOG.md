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

## 2026-09-08 — Surveys page overhaul and a dedicated Collections page

### Found

- Un-hiding the dead code above surfaced real clutter: two separate upload
  forms hitting the same endpoint, a "Named session" pre-creation form whose
  own runs list had no way to actually import data into a run it created
  (`POST /v1/ingestions` has never been called from the frontend — only its
  `GET` counterpart is), and collection creation living only on this page
  while collection listing/rename lived only on the admin-only Access page.

### Built

- Collections are now managed on their own nav page ("Collections"), reachable
  by analyst and admin roles (viewer/auditor see the list only, matching
  `POST /v1/survey-areas`'s existing `protected("analyst")` bar). It combines
  what was previously split across the dead Surveys form and the admin-only
  panel: create (with the coarse/exact precision choice), list with run/device
  counts, and rename (still admin-only, unchanged permission). Removed from
  Administration, which now only has account management, OUI enrichment, and
  retention.
- Surveys is down to two cards: one merged upload form (source format, file,
  optional session name, optional collection — pick an existing one or create
  new inline, same pattern as the bulk-file selector) and the existing recent-
  captures list with bulk filing. Removed the redundant second upload form and
  the non-functional "Named session" form entirely, along with their four
  handler functions and the now-unused `List` component.

### Boundary

- A collection created inline from the upload form is always coarse
  precision (matching `/v1/imports`'s existing find-or-create behavior); an
  exact-precision collection must be created ahead of time on the Collections
  page, then picked from the dropdown at import time.
- Still no browser-driven test for either page; this was found and fixed from
  a screenshot, same as the two UI issues before it in this log.

## 2026-09-08 — Untrimmed collection names created ambiguous duplicates

### Found

- `create_area` never trimmed `name` before storing it, so "Test 1" and
  "Test 1 " (trailing space) are distinct, both-valid rows under the existing
  unique constraint on `collections.name` — a real duplicate a user can't
  visually detect in a `<select>`. `quick_import`'s collection-assignment path
  *does* `.strip()` the incoming name before its find-or-create lookup, so a
  value carried forward from a `<select>` populated with an untrimmed stored
  name silently failed to match the original row and created a second,
  always-coarse one instead. This is exactly what happened live: an "exact"
  collection was created with a trailing space, an import meant for it landed
  in a new coarse duplicate instead, and the run's devices never got an
  encrypted address — with the OUI-attribution rate also near zero, because
  this was on a freshly reset database and nobody had re-populated the OUI
  catalog yet (`oui_assignments` was confirmed empty; enrichment fell back to
  the tiny built-in seed list in `app/oui.py`, not a code regression).

### Fixed

- `create_area` now trims `name`/`authorization_ref` and rejects an
  already-used (trimmed) name with a 409, matching `rename_area`'s existing
  behavior (which already trimmed and checked, and is why the user's own
  rename attempt correctly failed with "Another collection already uses that
  name" — both stray names collided once trimmed).

### Boundary

- The two existing duplicate rows in the live database were not merged or
  deleted automatically — no delete-collection action exists yet, and
  reassigning the run to the correct collection would not retroactively
  encrypt its devices' addresses regardless, since that only happens at
  ingestion time. The fix prevents recurrence; the existing pair needs a
  manual rename (or a fresh import into the already-empty exact one) to
  resolve.
- Added `test_create_area_trims_whitespace_and_rejects_names_that_collide_after_trimming`.
  The suite passed 21/21 after the change.

## 2026-09-08 — On-demand run deletion, and a real orphan-cleanup bug in it

### Found

- `DELETE /v1/survey-runs/{run_id}` (admin-only, calls the same
  `purge_run_data` the age-based retention sweep uses) already existed in the
  backend but was never called from the frontend — the third dead/unreachable
  backend capability found this session, after the two dead Surveys forms and
  the unused `POST /v1/ingestions`.
- Wiring it up to test it surfaced a real bug in `purge_run_data` itself: its
  orphaned-device cleanup filtered on `Device.survey_area_id == area_id`, but
  `Device.survey_area_id` (`collection_id`) is never populated by
  `process_ingestion` for any real device — confirmed directly against the
  live database (every one of 25,498 devices has `collection_id = NULL`, even
  though their run is filed into collection id 2). For any run filed into a
  named collection, that filter can never match a real device row, so
  deleting or retention-purging such a run left its now-orphaned devices
  behind as permanent zero-observation ghosts. This affects the existing
  age-based retention purge too, not just the new on-demand path — it was
  latent until something actually tried to delete a *filed* run's data and
  checked the device table afterward.

### Fixed

- `purge_run_data` now scopes orphan detection to the specific devices that
  had observations in the run being deleted (found before the observations
  are removed), then checks each for zero remaining observations anywhere —
  correct regardless of collection, and cheaper than the old area-wide scan.
- Added a "Delete" button (admin-only, `window.confirm`-gated) to each row in
  the Surveys "Recent captures" list.

### Boundary

- This is a hard, permanent delete with no retention window or preview step,
  unlike the age-based sweep. It exists specifically for correcting mistakes
  like the duplicate-collection test data above, not as a routine cleanup
  tool.

### Evidence

- Added `test_purge_run_data_removes_orphaned_devices_even_when_filed_into_a_collection`,
  which deliberately constructs its device the way real ingestion does (no
  `survey_area_id` set) rather than the way the existing retention test does
  (which happened to set it, masking this exact bug). The suite passed 22/22
  after the change.

## 2026-09-08 — Code review audit: baselines/anomalies never worked on real data

### Found

Ran `/code-review` at high effort across `app/` and the frontend, then
verified each finding directly rather than taking them on faith.

- **Confirmed, severe, pre-existing:** `baseline_expectations` and
  `build_anomalies` both filtered by `Device.survey_area_id == area_id` — the
  same column already established this session to be permanently NULL for
  every device real ingestion creates. Since `BaselineInput.survey_area_id`
  is always a real area (never null), this filter matched zero rows for any
  baseline built from real data: `baseline_expectations` returned empty
  devices/vendors/categories/cells/hours/profiles, and `build_anomalies`
  found zero observations, so it could never emit a single finding. The
  entire Phase 2 anomaly-detection feature has not worked against real
  imported data since it was built — masked entirely by
  `test_frozen_baseline_flags_later_novel_device`, which (like the
  `purge_run_data` test before it) manually set `Device.survey_area_id` in a
  way real ingestion never does.
- **Confirmed, introduced this session, now fixed:** `CollectionsPage`'s
  `create()`/`rename()` called both local `setNote(...)` and the parent's
  `reload()`; `reload()` bumps a `refresh` counter that's part of
  `WorkspaceBoundary`'s `key`, remounting the current page and wiping the
  just-set local note almost immediately. Every other page avoids this by
  using a `say` callback into the parent's note state (rendered outside the
  remounting boundary) instead of local state — `CollectionsPage` was the one
  page that didn't follow that pattern.
- **Confirmed, low severity:** `create_area`/`rename_area`'s duplicate-name
  check was a check-then-insert, not atomic — two near-simultaneous requests
  with the same name could both pass the check and the second would hit an
  unhandled `IntegrityError` (500) instead of the intended 409.
- **Plausible, low practical impact right now:** the upload form's collection
  picker uses the sentinel string `"__new__"` to mean "create new," which
  would misbehave if a collection were ever actually named `"__new__"`. Not
  fixed — collision is vanishingly unlikely and the fix (a separate
  create-new toggle instead of an overloaded select value) touches three call
  sites for a real-world risk near zero.
- **Plausible, currently moot:** removing the "Named session" form also
  removed the only "Mark complete" control. Not fixed — the only run-creation
  path left in the UI (`quick_import`) already sets `completed=True`
  automatically, so nothing in the current UI can create an incomplete run to
  get stuck. This only matters if `POST /v1/survey-runs` (still live, still
  unreachable from the UI) is ever called directly.

### Fixed

- `baseline_expectations` now scopes purely by the already-area-validated
  `run_ids` (no `Device` join condition needed); `build_anomalies` now joins
  `SurveyRun` and filters `SurveyRun.survey_area_id`, matching the join
  pattern `filtered_observations` already uses correctly elsewhere in this
  file.
- `CollectionsPage` now takes a `say` prop and uses it instead of local note
  state, matching `Surveys`.
- `create_area` and `rename_area` now catch `IntegrityError` on commit and
  return a 409, closing the race the pre-check alone couldn't.

### Evidence

- `test_frozen_baseline_flags_later_novel_device` updated to construct
  devices without `survey_area_id`, matching real ingestion; it still passes,
  now actually exercising the fixed code path. No existing baselines were in
  the database to need recreation (checked directly: zero rows). The suite
  passed 22/22 after the change.

## 2026-09-08 — Static UI pass: one real regression fixed

Diffed every `className` used in `main.tsx` against every selector defined in
`style.css` to find dead/typo'd class references, then checked each
recently-touched component's markup against its CSS by hand (no browser
available in this environment).

### Found and fixed

- Recent Captures' checkbox rows wrap the session name in `<label
  className="check"><b>{run.name}</b></label>` for the checkbox layout, but
  `.list > div > b`'s color/weight rule only matches a *direct* child `b` —
  nesting it inside the label silently opted it out, so session names
  rendered in the list's plain muted gray instead of the bold, brighter color
  every other list item's name uses. Added a `.list .check b` rule scoped to
  color/weight only (not `display`, which the flex checkbox row already
  handles correctly on its own).

### Noted, not fixed (cosmetic, no visible breakage)

- The pre-login "Opening Signal Ledger…" text (`.loading`) has no dedicated
  style — plain body text, not broken, just unpolished.
- `CollectionsPage`'s admin rename `<form className="inline-form">` inherits
  a `margin-top: 10px` meant to separate it from a name line above; here it's
  usually the first element in its row, so there's a small, likely
  imperceptible extra gap at the top of each row.
- `.cards` is now dead CSS (its only JSX usage was removed in the Surveys
  rewrite) — no visible effect, just unused weight.

## 2026-09-08 — First real browser pass: two more confirmed bugs, both fixed

The user provided real login credentials for their local instance. Drove it
headlessly with Playwright (Chromium) instead of reasoning about markup
statically — logged in, screenshotted every page, and cross-checked against
the live database.

### Found and fixed

- **`survey_area_id`/`collection_id` frontend mismatch, severe.**
  `SurveyRun.survey_area_id` (and the same pattern on `Device`, `Baseline`,
  `Anomaly`) is a Python-only synonym for the real `collection_id` column;
  `dump()` walks `__table__.columns`, so every JSON response actually carries
  `collection_id`, never `survey_area_id`. The frontend read the wrong key in
  three places: Surveys showed every filed run as "Unfiled" regardless of its
  real collection; Coverage's "Import session" dropdown filtered to zero
  options whenever a specific collection was selected; Baselines' completed-
  runs checklist was always empty once an area was chosen — making it
  **impossible to create a baseline through the UI at all**, on top of the
  baseline_expectations/build_anomalies bug found in the prior review. Write
  paths (`RunInput.survey_area_id`, `BaselineInput.survey_area_id`) were
  already correct and untouched — only read sites needed the fix. Verified
  live: the session dropdown now lists the real session once its collection
  is selected, the Baselines checklist now shows the completed run, and
  Surveys now shows "Test 1" instead of "Unfiled" for the filed capture.
  Added `test_survey_run_json_exposes_collection_id_not_the_survey_area_id_synonym`
  to lock in the actual wire shape. Suite passed 24/24.
- **Vendor breakdown chart, legibility.** With 25,492 of 25,498 devices
  unattributable, the bar chart's one dominant bar reduced every real vendor
  to an invisible or near-invisible sliver, and "Leading vendor: unattributable,
  100%" was a meaningless headline. The chart and "leading vendor" callout
  now exclude the unattributable bucket (still shown in the full table below,
  and called out in the summary line and its own share is now computed
  against attributed devices only, not total devices, so it reads
  meaningfully instead of rounding to 0%.

### Noted, not fixed

- Two console errors during the pass: a `401` on `/v1/me` before login (
  expected — that's how the app detects "not signed in") and one `404` seen
  once and not reproduced on a second run (likely a stray favicon request).
- Retention panel shows literal "…" for the day counts until "Preview
  candidates" is clicked, since that call is what populates them. Not
  broken, just eager-vs-lazy — a pre-existing choice, not touched.

## 2026-09-08 — Command center: decoupled the two dashboard columns

### Found

- The dashboard's two-column layout was a single CSS grid with implicit row
  pairing: Observation footprint (map) paired with Protocol distribution in
  row 1, Discovery activity with Changes to investigate in row 2. Grid row
  auto-sizing meant each row's height was set independently of the other
  rows, but *within* a row the shorter card still got stretched to match the
  taller one (default `align-items: stretch`) — so the map's height was
  effectively capped near whatever the much shorter Protocol distribution
  card needed, not what the map itself needed to be legible. That's why it
  read as squished even after the earlier letterboxing fix.

### Fixed

- Replaced the single grid with two independent flex columns
  (`.dashboard-columns` / `.dashboard-column.wide` / `.dashboard-column
  .narrow`, `align-items: flex-start` so neither column stretches to match
  the other's height) each stacking its own cards: left column is
  Observation footprint + Discovery activity, right column is Protocol
  distribution + Changes to investigate. Recent imports stays full-width
  below both, now as a plain sibling instead of a grid-column-spanning
  hack.
- With the map no longer height-capped by its row-mate, gave it a taller
  aspect ratio (1120:460, up from 1120:300) and updated `LocalMap`'s
  internal `compact` viewBox to match, so the plot area actually fills the
  extra height instead of reintroducing letterboxing.

### Evidence

- Verified visually via the same Playwright screenshot pass: the map is
  markedly taller and more legible, Protocol distribution keeps its own
  natural (shorter) height instead of stretching into dead space, and the
  two columns now end at independent heights above the full-width Recent
  imports row.

## 2026-09-08 — Command center: map now fills its column instead of a fixed ratio

Moved Discovery activity into the right (narrow) column, alongside Protocol
distribution and Changes to investigate; the left (wide) column now holds
only the map. Since the map is now the sole item in its column, the intent
was for it to grow to fill whatever height the (now taller, three-card)
right column ends up needing, rather than sitting at a fixed size.

### Built

- Reverted `.dashboard-columns` to default `align-items: stretch`, so the
  two columns share the taller column's total height (now the right column,
  with three stacked cards) - then `.dashboard-column.wide .panel.landscape
  { flex: 1 }` lets the lone map panel grow into that full stretched height,
  with a 460px floor so it never gets too short if the right column is ever
  shorter.
- A fixed `aspect-ratio` can't fill an arbitrary flex-allocated height
  correctly - it either letterboxes (if the box's actual aspect doesn't
  match) or, worse, sizes purely from width and ignores the extra height
  entirely, which would have made this change a no-op. So `LocalMap`
  dropped the fixed `compact` viewBox dimensions for a `ResizeObserver` on
  its canvas wrapper, measuring the container's actual rendered box and
  redrawing the plot's viewBox to match exactly - the grid/points/axes now
  regenerate at whatever size the flexbox gives them, with no letterboxing
  possible since viewBox always equals the real box. The non-compact
  (Coverage page) map path is untouched - only `compact` mode measures.

### Evidence

- Verified visually: the map now visibly fills the full height of the
  three-card right column with no letterboxing or dead space, confirming
  the resize-driven viewBox actually adapts rather than just padding
  around a fixed-ratio drawing.

## 2026-09-08 — Coverage page map: bumped height, and fixed a bug in yesterday's fix

### Found

- Measuring the Coverage page's map precisely (not just eyeballing a
  screenshot) showed the SVG box was 1248x480 but the actual visible plot
  only rendered at 828x480 — roughly 420px of invisible pillarboxing on the
  sides, the same class of bug fixed earlier for the dashboard, just never
  applied here. `max-height: 480px` was the binding constraint, and the
  fixed 800:464 viewBox didn't match the box it was actually given.
- Extending the same ResizeObserver approach to this (previously
  aspect-ratio-based) path surfaced a genuine bug in the observer logic
  itself: on the Coverage page, `cells` starts empty before the first
  fetch resolves, so `LocalMap`'s own internal `!points.length` early
  return renders a plain "no data" placeholder on first mount - the canvas
  div doesn't exist yet, so the effect's `if (!canvasRef.current) return`
  fires immediately, and with an empty dependency array it never re-ran
  once real data arrived and the canvas finally mounted. Confirmed directly
  (not assumed): the rendered `viewBox` stayed frozen at the initial
  `1120 460` fallback indefinitely. The dashboard's version of this
  component happened to dodge the bug only because its parent gates
  rendering `<LocalMap>` at all behind its own `ready` flag, so LocalMap's
  first-ever render already has real data.

### Fixed

- Moved the `points` computation above the effect and made the effect
  depend on `points.length > 0`, so it re-attaches once the canvas actually
  mounts, regardless of whether that's on the first render or a later one.
- Gave the non-compact map a real height (`.local-map-canvas { height:
  640px }`, up from an effective ~480px) now that the box is guaranteed to
  render without letterboxing at any size.
- Removed a stale small-screen media query (`.landscape .local-map svg {
  height: auto; min-height: 220px }`) left over from the old fixed-ratio
  approach; it now conflicts with the resize-driven sizing rather than
  helping it, and the panel's own `min-height: 460px` already provides a
  sane floor at any width.

### Evidence

- Verified precisely (not just visually) via bounding-box and `viewBox`
  attribute checks: Coverage's rendered plot now spans the full 1248x640
  box with zero pillarboxing, and the dashboard map still measures
  correctly too (773x709, matching its column's real height - a portrait-
  ish shape here is correct, not a bug, since the right column is now
  taller than it is wide). Backend suite unaffected (23/23, no backend
  changes this round).

## 2026-09-08 — Coverage map: aspect-ratio instead of a fixed height

A fixed pixel height (700px) was the wrong tool for "match the dashboard
map's shape" - the dashboard's map isn't set to any specific height, it's
whatever a flex-fill column happens to need, and a hardcoded height on
Coverage wouldn't track that. Since the ResizeObserver-driven sizing means
the box's *shape* no longer matters for correctness (viewBox always matches
whatever box it's given, so nothing letterboxes regardless of ratio),
switched `.local-map-canvas` to `aspect-ratio: 1 / 1` instead - a true
responsive square, consistent with the dashboard map's own roughly-square
proportions (773x709) without hardcoding either map to the other's
incidental pixel size. The `.landscape` (dashboard) override resets
`aspect-ratio: auto` so its flex-fill behavior is unaffected.

Verified directly: Coverage's map now measures exactly 1248x1248 (viewBox
matches the box, no pillarboxing) at this viewport width, and stays square
at any width since it's a ratio, not a fixed number.

## 2026-09-08 — Local map: cleaner point/track rendering, matching CARTO's paint

### Found

- Comparing our SVG map against the CARTO/MapLibre basemap rendering the
  exact same `capture-track`/`capture-halo`/`capture-point` data side by
  side, the CARTO version reads as a clean tube-shaped route with small,
  consistent markers; ours reads as a cluster of oversized, bright-rimmed
  bubbles wherever coarse cells sit close together (0.001 degree apart is
  often just a few px). The paint values were the difference, not the
  underlying geometry: CARTO's track line is opaque and prominent
  (`line-opacity: .75`, width 3); ours was faint (`stroke-opacity: .42`,
  width 2) and got visually buried under the point circles. CARTO's point
  marker is a small, fixed radius of 4 with a dark, subtle stroke; ours
  scaled the *point itself* (not just the halo) up to a 27px radius with a
  bright near-white stroke (`#d7f5bb`), so overlapping cells produced a
  chain of loud rings instead of one coherent shape.

### Fixed

- Track line now matches CARTO's paint exactly: `stroke: #5a8d44;
  stroke-opacity: .75; stroke-width: 3`.
- Point markers are now a small fixed radius (4, matching CARTO) with a
  dark stroke (`#325025`) instead of scaling with count and carrying a
  bright rim; density is now encoded *only* by the halo, matching how
  CARTO splits the same encoding across its two circle layers.
- Halo radius scale reduced (max ~22, down from ~31) and given CARTO's
  subtle dark stroke (`#436c33`) and a touch more opacity (.28, up from
  .1) so it reads as a soft density glow rather than a near-invisible
  fill.
- `EDGE_PAD` (the margin that keeps points off the axis labels) reduced
  from 31 to 22 to match the new, smaller maximum halo radius.

### Evidence

- Verified visually (zoomed crop of the same route peak used in the CARTO
  comparison): the cluster of overlapping bright rings is gone, replaced
  by a continuous tube-like line with small distinct dots, matching the
  CARTO rendering's character. Backend suite unaffected (23/23, no
  backend changes this round).

## 2026-09-08 — Sidebar scroll fix, and vendor-suggestion search

### Built

- **Sidebar**: on short viewports, the nav item list could overflow the
  fixed-height sidebar with nowhere for the extra items to go, potentially
  pushing the "Private by design" footer and account controls out of
  reach. `.sidebar` now clips (`overflow: hidden`) and only its `<nav>`
  scrolls internally (`flex: 1 1 auto; min-height: 0; overflow-y: auto`),
  so the brand header stays pinned at the top and the footer/profile
  block stays pinned at the bottom regardless of how many nav items there
  are. Verified directly (not just visually): at a 520px-tall viewport,
  `nav.scrollHeight` (556px) exceeds `nav.clientHeight` (186px) with
  `overflow-y: auto` active, and scrolling the nav to its end leaves the
  header and footer exactly where they were.
- **Vendor-suggestion search**: the "OUI organization" filter on both
  Coverage and Inventory was a blind free-text box requiring the exact
  matched string. Both now fetch the real vendor list from the existing
  `/v1/devices/vendors` endpoint once on mount and offer it through an
  HTML `<datalist>` (`list="coverage-vendor-options"` /
  `"inventory-vendor-options"`) - native browser autocomplete-as-you-type
  against real matched organization names, with free-text substring
  search still working as a fallback for anything not in the list. No new
  dependency; reuses data the Vendor Breakdown page already needed.

### Boundary

- `<datalist>` filtering is a plain substring/prefix match per the
  browser, not true fuzzy (typo-tolerant) matching - a real fuzzy-match
  combobox would need a custom component, which felt like more UI weight
  than this filter warrants right now.

### Evidence

- Verified the datalist is populated with real data end to end: after an
  IEEE catalog refresh, both pages' `#coverage-vendor-options` and
  `#inventory-vendor-options` list the same 300+ real OUI organizations
  (Cisco Systems, Apple, Raspberry Pi Foundation, etc.), not just the
  seed-list fallback. Backend suite unaffected (23/23, no backend changes
  this round).

## 2026-09-08 — Purge row layout, Collections rename/delete

### Built

- Retention's confirm input and "Purge reviewed candidates" button now sit
  side by side (a `.purge-row` flex wrapper) instead of stacking full-width,
  with a normal gap between them - the button had been touching the
  input/notice below it with no breathing room.
- Collections' "Rename" button was `.quiet` - fully transparent until
  hovered, so it looked unstyled/inert at rest (confirmed: `.quiet`'s
  resting state has no border or background at all, only gaining one on
  `:hover`). Switched to `.secondary`, which has a visible border/background
  in every state.
- Added collection deletion: `DELETE /v1/survey-areas/{id}` (admin-only,
  audited), rejecting with a 409 if the collection still has any runs
  filed into it - matching the same "won't silently orphan data" posture as
  the existing run-deletion endpoint, and sidestepping any FK-cascade
  design questions by simply requiring an empty collection first. The
  Collections page now shows a "Delete" button (red `.secondary.danger`
  variant, `window.confirm`-gated) next to Rename, disabled with a tooltip
  when `run_count > 0`.
- `.inline-form`'s `max-width` bumped 390px -> 480px to comfortably fit an
  input plus two buttons now that Rename has a Delete neighbor; it had
  exactly one usage in the whole file, so this couldn't affect anything
  else.

### Evidence

- Added `test_delete_area_rejects_a_collection_with_runs_but_allows_an_empty_one`.
  Suite passed 24/24. Verified visually: a collection with 1 run shows
  Delete disabled/greyed; an empty collection shows it enabled with the red
  danger styling, and Rename is now a clearly visible button in both rows'
  resting state.

## 2026-09-08 — A vanishing-notice bug, and an import progress toast

### Found

- Reproduced directly (sampling the DOM every 100ms after a rename): App's
  `load()` unconditionally called `setNote("")` partway through its own
  fetch chain. Any action that calls `say(message)` immediately followed by
  `reload()` - which is most of them - had its message wiped out roughly
  100-300ms later, as soon as `load()`'s own `Promise.all` resolved. This
  almost certainly compounds the "did that even work?" feeling behind this
  session's toast request: even actions that already reported success were
  silently erasing their own confirmation moments later. Removed the line;
  nav clicks and the dismiss button already clear the note explicitly where
  that's actually wanted.

### Built

- Added a persistent, app-level import progress toast (bottom-right,
  indeterminate progress bar) for the one genuinely long-running action in
  the app: Surveys' capture upload, which polls for up to two minutes.
  `importing` state now lives on `App` (not the Surveys component), so the
  toast survives navigating to a different page mid-import instead of
  disappearing with the component that started it - the background poll
  loop is a plain async closure that keeps running and updating shared
  state regardless of what's currently rendered.
- The final result (accepted/rejected counts) still goes through the
  existing `say()`/notice-banner path, now that it actually persists;  the
  toast's only job is "something is still working," not the outcome.

### Evidence

- Verified end-to-end: uploading a real file shows the toast immediately,
  navigating to Command center mid-import keeps it visible, and once the
  backend job completes the toast disappears and "Import complete: 1
  accepted." appears and *stays* - visible even after navigating away,
  confirming the vanishing-notice fix and the toast both work together
  correctly. Confirmed data actually changed (capture sessions 1 -> 2,
  observations +1) rather than just checking UI state. Backend suite
  unaffected (24/24, no backend changes this round).

## 2026-09-08 — Device evidence: first/last seen, collection, and a second collection_id near-miss

### Found

- User reported that after filing a device into an exact-precision
  collection, the Device evidence page still showed nothing tying it back
  to that collection, and flagged the page as generally thin (no seen
  dates, no collection). While implementing this, I initially wrote it the
  obvious way - `areas.find(area => area.id === device.collection_id)` -
  and caught mid-implementation that this reads `Device.collection_id`,
  the same column already proven this session (baseline/anomaly fix) to be
  permanently NULL for every real device, since real ingestion never
  populates it. Would have shipped "Unfiled" for every device that actually
  has a filed collection.

### Built

- `device_detail()` now derives a `collections: list[str]` field by joining
  Observation -> SurveyRun -> SurveyArea and taking the distinct area names
  actually touched by that device's own observations, instead of trusting
  the device row's own (dead) column.
- Device evidence page now shows "First seen: ... · Last seen: ... ·
  Collection: ..." (joining multiple collections with ", ", falling back to
  "Unfiled" only when a device truly has none), plus a note for admins when
  a device has no stored address at all ("captured under coarse-precision
  collections only").
- Removed the frontend's speculative `collection_id` field and the
  now-unnecessary `areas` prop from `DeviceEvidence` before any of it
  shipped.

### Evidence

- Added `test_device_detail_derives_collections_via_observations_not_the_device_column`,
  which deliberately constructs its Device without setting
  `survey_area_id` (matching real ingestion) to prove the derivation
  doesn't depend on that column. Suite passed 25/25.
- Verified live via Playwright against a real device previously filed into
  the "Test 1" collection: the evidence page now reads "Collection: Test
  1" (not "Unfiled"), and clicking Reveal address still correctly shows
  the real MAC (`32:B4:B8:2A:82:0A`) alongside it - both pieces of
  evidence now visible on the same page instead of the address living in
  isolation.
