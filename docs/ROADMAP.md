# Signal Ledger — Delivery Roadmap

**Source of requirements:** the original `plan.md` is not present in this
checkout; current policy decisions are recorded in [`POLICIES.md`](POLICIES.md)
and [`DESIGN.md`](DESIGN.md).
**How to use this file:** check an item only after the implementation and its
named validation both exist. “Implemented” is not “production hardened.”

## Current position

Phase 1 has a working private-operator vertical slice with successful
authorized WiGLE and Kismet imports. Phase 2 now has its first working
baseline-to-review loop; hardening and policy defaults remain explicit gates.

## Phase 0 — discovery and guardrails

- [x] Preserve the product, privacy, and non-active-collection boundary.
- [x] Establish a minimal Docker-stack architecture.
- [x] Add parser fixtures and unit tests for a minimal WiGLE export.
- [x] Add a fixture for the WiGLE 1.6 metadata/header variant.
- [x] Add a fixture for the initial Kismet-shaped adapter input.
- [x] Validate the actual authorized WiGLE variant through an import job.
- [x] Validate and fixture an authorized Kismet 2025.09 native SQLite log
  (schema v9) through its summary-device table only.
- [x] Set written retention, export, and area-precision policies.
- [x] Define an approved survey-area polygon format and acceptance checks.

**Exit gate:** real authorized fixtures from both source families, documented
policy defaults, and deterministic parser reports in CI.

## Phase 1 — ingestion and inventory MVP

### Foundation and access

- [x] React/TypeScript frontend and FastAPI backend.
- [x] Three-container Compose stack: app, PostgreSQL/PostGIS, Redis.
- [x] First-run administrator creation and password login.
- [x] Opaque HttpOnly persistent session cookies and server-side session hashes.
- [x] Administrator-created users and four bounded roles.
- [x] Direct capture import with filename-derived sessions; optional collections,
  manual session labels, and coverage estimates for organization when needed.
- [x] Audit entries for authentication, area/run creation, uploads, retries,
  and user creation.
- [x] User disable/enable and administrator session revocation controls.
- [x] Redis-backed request-rate limit and browser security headers.
- [x] Password reset/change flow and TLS/secure-cookie production deployment
  runbook/configuration test.

### Ingestion

- [x] Asynchronous upload jobs via Redis/RQ.
- [x] File extension, size, empty-file, source selection, and identifier checks.
- [x] Content-hash idempotency and within-upload deduplication.
- [x] WiGLE parser including the tested 1.6 metadata row.
- [x] Kismet adapter for the initial shaped fixture and native 2025.09 SQLite
  summary-device logs; packet/data blob tables are intentionally ignored.
- [x] Site-scoped HMAC device tokens; no normalized full MAC column.
- [x] Locally administered addresses labeled unattributable.
- [x] Versioned job report: accepted, rejected, skipped, source, parser version,
  and collector coverage.
- [x] Batched processing demonstrated on the authorized real WiGLE import.
- [ ] Restricted parser isolation, malware scan, and robust MIME validation.
- [ ] Encrypted or external object storage with short retention configuration.
- [x] Downloadable, human-readable ingestion report.
- [x] Location-completeness, parser-version, and rejection-reason report context.
- [x] Integration test: upload → worker → report → device/coverage APIs.

### Explorer

- [x] Overview with import totals and recent import history.
- [x] Inventory table with area and OUI-organization filters.
- [x] Coarse-cell density and protocol-mix view.
- [x] Interactive local coarse map, filterable to a collection run or a selected
  device’s sightings, without third-party map-tile requests.
- [x] Coarse receiver-track overlay, segmented across sessions and time gaps;
  it is distinct from device sightings.
- [x] API pagination parameters and bounded list limits.
- [x] UI pagination, loading/empty/error states, and import history detail view.
- [x] Device detail/evidence view and observation explorer.
- [x] Bounded server-side filters for time, protocol, category, RSSI, quality,
  and vendor across inventory, observations, map, and analytics APIs.
- [x] Optional MapLibre basemap mode with an explicit privacy decision for any
  external tile provider; the local coarse map remains the default.
- [x] Time-series, category/vendor, and quality/coverage overlays.
- [x] Replace in-memory analytics aggregation with grouped SQL queries.
- [x] Populate PostGIS geometry during new ingestion while retaining coarse-cell
  UI defaults.
- [x] Complete-run UI action and clear run lifecycle status.

### Enrichment and policy

- [x] Versioned local OUI catalog with administrator CSV import, provenance-safe
  organization label, and re-enrichment of existing devices.
- [x] Reviewed IEEE MA-L import contract: retain only prefix and organization,
  record source hash/version, and ignore non-MA-L registry rows.
- [x] Transparent category-rule engine using OUI, device name/type, SSID,
  protocol, and privacy-safe MAC scope, with confidence, evidence, and review
  override.
- [x] Orthogonal, explainable device-role/context rules for POS, security,
  smart-home, industrial/OT, medical, and guest-network signals, with
  inventory filtering and retained evidence.
- [x] Area polygon validation/enforcement and exact-location privilege/audit path.
- [x] Saved-filter UI and audit-event UI.

**Exit gate:** a user can create an authorized area/run, import each supported
fixture repeatably, understand the report, filter and inspect results, and use
a coarse map/analytics view. Automated integration tests cover the path.

## Phase 2 — baselines and explainable findings

- [x] Baseline creation from selected completed runs.
- [x] Frozen baseline version, training-run list, coverage mean, and derived
  device/vendor/category/cell/hour/profile expectations.
- [x] Coverage-quality findings kept distinct from security findings.
- [x] Explainable novel-device rule.
- [x] Explainable novel-vendor rule with valid-OUI safeguards.
- [x] Explainable spatial outlier rule using coarse cells.
- [x] Explainable temporal outlier rule with baseline hour windows.
- [x] Explainable Wi-Fi profile-change rule preserving source facts.
- [x] Anomaly queue with score, confidence, explanation, and disposition.
- [x] Audit trail for baseline creation/evaluation and dispositions.
- [x] Analyst disposition notes and evidence links in the UI.
- [ ] End-to-end integration tests from upload through every finding type.

**Exit gate:** selected runs yield a reproducible baseline and reviewable,
non-automated findings with evidence and explanations.

## Phase 3 — hardening and operational learning

- [x] Admin-reviewed retention/deletion workflow removes raw upload, observations,
  unreferenced device tokens, derived cells, and affected baseline/anomaly material; test it.
- [x] Admin-editable retention windows (raw/normalized) with selectable presets
  (30/90/180 days, custom), replacing the current env-var-only
  `RAW_RETENTION_DAYS`/`NORMALIZED_RETENTION_DAYS` read-only display; needs a
  persisted settings row, an audited update endpoint, and the purge sweep
  reading from it instead of the environment.
- [x] Backup/restore tooling and operational runbook; a disposable restore
  drill verifies a readable archive and matching migration/device/observation/
  job counts without replacing the active database.
- [x] HMAC-key rotation and re-baselining procedure; a disposable re-ingestion
  drill verifies that the same source creates a distinct token epoch after a
  secret change. Production secret-store cutover remains a deployment action.
- [x] Load/performance test for a realistic synthetic import and explorer
  volume: 5,000 rows completed ingestion in 4.622 seconds and inventory/map
  queries in 0.024 seconds on the disposable local Compose stack.
- [x] Parser regression fixtures for JSON-array Kismet source variant.
- [x] First hardening pass: headers, session revocation, request limiting, secret
  handling, and deliberate destructive-operation controls.
- [x] Accessibility and responsive UI pass; see Workflow Phase D browser
  acceptance below.
- [x] Add false-positive measurement by area/time window; threshold tuning still
  requires representative review volume.
- [x] Deployment runbook, dependency-aware health, structured redacted logs,
  and a read-only post-upgrade verification procedure.

**Exit gate:** the system can be operated, backed up, restored, cleaned up,
and evolved without weakening the privacy or authorization boundaries.

## Improvement program — inventory intelligence

These workstreams extend the current category and role evidence layer without
turning inferred labels into identity or security verdicts.

- [x] Durable evidence review queue for unknown/low-confidence devices, with
  category/role evidence, analyst disposition, notes, references, audit
  events, evidence-quality buckets, repeated-signature grouping, and group
  dispositions. Review context is optional, no-signal groups support an
  `insufficient_evidence` disposition, and single-device groups expose an
  audited category override picker. The queue is paginated at 24 groups per
  page, and the SPA pages are addressable with browser back/forward support.
  Validation: 47 containerized regression tests, production build, and live
  actionable/no-signal count check.
- [x] Role/category overview dashboard with counts, confidence, top evidence,
  overlap handling, and click-through inventory filters. Validation: 47
  containerized tests, production frontend build, and live summary payload
  check.
- [x] Rule feedback loop that records analyst corrections as reviewable,
  versioned rule proposals; no automatic rule promotion.
- [x] Privacy-safe device fingerprints using vendor, name/type, protocol,
  security, timing, and coarse observation patterns; output is a similarity
  suggestion, not an identity merge.
- [x] Import comparison view showing new, returning, disappeared, and changed
  devices between completed runs, with coverage context.
- [x] Saved inventory views for category/vendor/role/attribution filters,
  including unknown, POS, guest-network, automotive, and review workflows.
- [x] Privacy-safe device CSV exports containing pseudonymous tokens,
  classifications, roles, confidence, and provenance; never raw MACs, HMAC
  secrets, or exact coordinates by default.

  Validation: 47 containerized tests, production frontend build, live health
  check, and migration `0013_rule_proposals` applied.

**Improvement exit gate:** an analyst can move from a new import to a bounded
review queue, understand why each item was prioritized, record a disposition,
compare it with prior runs, and export only policy-approved evidence.

## Workflow reliability and command-center program

This program follows the frontend/workflow review in
[`FRONTEND_REVIEW_2026-09-09.md`](FRONTEND_REVIEW_2026-09-09.md). Each phase
must be completed end to end: backend contract, frontend behavior, focused
regression coverage, production build, and authenticated browser acceptance.
Do not mark a phase complete from a visual review or a build alone.

### Phase A — trustworthy import and review decisions

- [x] A capture session becomes eligible for comparison/baselines only after
  its ingestion job completes; queued, processing, failed, and duplicate
  uploads remain visibly distinct in the import history.
- [x] A group disposition applies only to the device membership returned for
  the current review status and scope; audit detail reports that same count.
- [x] Changing a review status without editing its note/references preserves
  the existing context; clearing context is an explicit action.
- [x] Import status, review mutation, and failure paths have focused tests and
  authenticated browser acceptance.

**Exit gate:** met in the test instance on 2026-09-09. A rebuilt-image suite
ran 50 tests, including queued/complete/failed import transitions and review
scope/context regressions. Authenticated browser acceptance signed in, opened
the review queue, applied a bounded group disposition, and received its audited
success state. A failed or pending import cannot appear imported; a review
action cannot alter hidden members; a status-only change cannot erase context.

### Phase B — continuous investigation context

- [x] Applied collection/session/filter/sort/page state is encoded in a
  bookmarkable route and restored on back, forward, refresh, and return from
  device evidence.
- [x] Inventory, review, coverage, saved views, counts, and exports use the
  same applied query; bounded exports disclose their result count.
- [x] Drilldowns retain the source collection and filter scope.

**Exit gate:** an analyst can open evidence and return to the identical queue
or inventory selection, and an export cannot silently differ from the table.
Verified on the rebuilt local app: inventory category/page routing, review
status/bucket routing, coverage device/protocol/RSSI routing, and an inventory
device drilldown return. The export regression also asserts its requested
sort/direction in the generated CSV.

### Phase C — import-to-decision command center

- [x] A completed import opens a session summary with parser outcome, source,
  GPS completeness, observed period, and next actions.
- [x] Compatible run comparison explains new, returning, changed, and
  not-observed records with before/after retained evidence and collection
  comparability context.
- [x] Overview prioritizes the latest import outcome, limitations, and review
  work; map and lifetime totals remain available as secondary context.
- [x] Navigation is organized around Overview, Imports, Inventory, Coverage,
  Compare, and Review while retaining deep links to advanced tools.

**Exit gate:** a private operator can move from a completed import to a
reviewable change or evidence record without reconstructing scope manually.
Verified on the rebuilt local app: a completed WiGLE import opened its session
summary, then entered inventory at the exact `run_id` and collection scope.

### Phase D — efficient and accessible operations

- [x] Review prioritization states the retained evidence that makes an item
  actionable and keeps no-signal material out of the primary queue.
- [x] Inventory and review layouts remain usable at narrow desktop widths and
  200% zoom, with compact optional columns and clear mutation feedback.
- [x] Keyboard, focus, ARIA semantics, error/status announcements, and local
  map fallback behavior pass browser acceptance.

**Exit gate:** keyboard and assistive-technology users can operate the core
import, investigate, review, and export loop without hidden state or traps.
Verified on the rebuilt local app: keyboard focus reaches the workspace skip
link; review cards state their retained vendor/network evidence; the primary
queue separates no-signal material; and the Coverage explorer starts on the
private local grid with third-party tiles opt-in. At a 900px viewport, the
inventory retains Device, Category, Last seen, and Actions while compacting
secondary columns. Status feedback is announced politely and inventory headers
expose their table semantics.

## Immediate next build sequence

1. Add end-to-end upload-to-every-finding-type coverage and test it against a
   representative authorized dataset.
2. Finish restricted parser isolation, malware scanning, and an approved
   encrypted/external raw-object storage deployment.
3. Tune categorization thresholds from representative analyst feedback and
   perform the TLS/reverse-proxy and deployment-secret cutover on the intended
   production host.
