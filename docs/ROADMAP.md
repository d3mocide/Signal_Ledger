# Signal Ledger — Delivery Roadmap

**Source of requirements:** [`../plan.md`](../plan.md).  
**How to use this file:** check an item only after the implementation and its
named validation both exist. “Implemented” is not “production hardened.”

## Current position

Phase 0 is substantially complete for the first WiGLE format. Phase 1 has a
working vertical slice, including a successful authorized real-world WiGLE
import, but it is **not complete**. The next focused slice is to make the
existing Phase 1 explorer fully usable and testable before beginning baselines.

## Phase 0 — discovery and guardrails

- [x] Preserve the product, privacy, and non-active-collection boundary.
- [x] Establish a minimal Docker-stack architecture.
- [x] Add parser fixtures and unit tests for a minimal WiGLE export.
- [x] Add a fixture for the WiGLE 1.6 metadata/header variant.
- [x] Add a fixture for the initial Kismet-shaped adapter input.
- [x] Validate the actual authorized WiGLE variant through an import job.
- [ ] Obtain and fixture an authorized real Kismet export/version.
- [ ] Set written retention, export, and area-precision policies.
- [ ] Define an approved survey-area polygon format and acceptance checks.

**Exit gate:** real authorized fixtures from both source families, documented
policy defaults, and deterministic parser reports in CI.

## Phase 1 — ingestion and inventory MVP

### Foundation and access

- [x] React/TypeScript frontend and FastAPI backend.
- [x] Three-container Compose stack: app, PostgreSQL/PostGIS, Redis.
- [x] First-run administrator creation and password login.
- [x] Opaque HttpOnly persistent session cookies and server-side session hashes.
- [x] Administrator-created users and four bounded roles.
- [x] Survey areas and runs with authorization references and coverage estimate.
- [x] Audit entries for authentication, area/run creation, uploads, retries,
  and user creation.
- [ ] User disable/enable, session revocation, password reset/change flows.
- [ ] Rate limiting and login/upload abuse controls.
- [ ] TLS/secure-cookie production deployment guidance and configuration test.

### Ingestion

- [x] Asynchronous upload jobs via Redis/RQ.
- [x] File extension, size, empty-file, source selection, and identifier checks.
- [x] Content-hash idempotency and within-upload deduplication.
- [x] WiGLE parser including the tested 1.6 metadata row.
- [x] Initial Kismet adapter and unit fixture.
- [x] Site-scoped HMAC device tokens; no normalized full MAC column.
- [x] Locally administered addresses labeled unattributable.
- [x] Versioned job report: accepted, rejected, skipped, source, parser version,
  and collector coverage.
- [x] Batched processing demonstrated on the authorized real WiGLE import.
- [ ] Restricted parser isolation, malware scan, and robust MIME validation.
- [ ] Encrypted or external object storage with short retention configuration.
- [ ] Downloadable, human-readable ingestion report.
- [ ] Per-field quality/completeness report and schema/version warning UI.
- [ ] Integration test: upload → worker → report → device/coverage APIs.

### Explorer

- [x] Overview with import totals and recent import history.
- [x] Inventory table with area and OUI-organization filters.
- [x] Coarse-cell density and protocol-mix view.
- [x] Interactive local coarse map, filterable to a collection run or a selected
  device’s sightings, without third-party map-tile requests.
- [x] API pagination parameters and bounded list limits.
- [ ] UI pagination, loading/empty/error states, and import history detail view.
- [ ] Device detail/evidence view and observation explorer.
- [ ] Server-side filters for time, protocol, category, RSSI, confidence, and
  vendor consistently across inventory/map/analytics.
- [ ] Optional MapLibre basemap mode with an explicit privacy decision for any
  external tile provider; the local coarse map remains the default.
- [ ] Time-series, category/vendor, and quality/coverage overlays.
- [ ] Replace in-memory analytics aggregation with scalable grouped queries.
- [ ] Populate/query PostGIS geometry for the approved precision policy.
- [ ] Complete-run UI action and clear run lifecycle status.

### Enrichment and policy

- [x] Small offline OUI seed mapping and provenance-safe display label.
- [ ] Reviewed, versioned full IEEE OUI import and update procedure.
- [ ] Transparent category-rule engine, confidence, evidence, and review override.
- [ ] Area polygon validation/enforcement and exact-location privilege/audit path.
- [ ] Saved-filter UI and audit-event UI.

**Exit gate:** a user can create an authorized area/run, import each supported
fixture repeatably, understand the report, filter and inspect results, and use
a coarse map/analytics view. Automated integration tests cover the path.

## Phase 2 — baselines and explainable findings

- [ ] Baseline creation from selected completed runs.
- [ ] Frozen baseline version, training-run list, date/time policy, coverage
  threshold, and derived expectations.
- [ ] Coverage-quality findings kept distinct from security findings.
- [ ] Explainable novel-device rule.
- [ ] Explainable novel-vendor/category rule with valid OUI/repeat safeguards.
- [ ] Explainable spatial outlier rule using coarse cells.
- [ ] Explainable temporal outlier rule with sample thresholds.
- [ ] Explainable Wi-Fi profile-change rule preserving before/after facts.
- [ ] Anomaly queue, evidence, score components, confidence, notes, and
  analyst disposition.
- [ ] Audit trail for baseline and disposition changes.
- [ ] Integration tests from ingestion through each finding type.

**Exit gate:** selected runs yield a reproducible baseline and reviewable,
non-automated findings with evidence and explanations.

## Phase 3 — hardening and operational learning

- [ ] Retention/deletion workflow removes raw upload, observations, device
  tokens, derived cells, and affected baseline/anomaly material; test it.
- [ ] Backup and restore drill, including PostGIS data.
- [ ] HMAC-key rotation and documented re-baselining drill.
- [ ] Load/performance tests for realistic import and explorer volumes.
- [ ] Parser regression fixtures for new source variants.
- [ ] Security review: headers, CSRF/session posture, secret handling,
  least-privilege DB/volume settings, dependency updates.
- [ ] Accessibility and responsive UI pass.
- [ ] Measure false positives by area/time window and tune thresholds.
- [ ] Deployment runbook, monitoring, structured logs, and upgrade procedure.

**Exit gate:** the system can be operated, backed up, restored, cleaned up,
and evolved without weakening the privacy or authorization boundaries.

## Immediate next build sequence

1. Make the existing explorer comprehensible: import-history detail, UI
   pagination, device detail, and clear run completion state.
2. Add the real coarse map and consistent server-side filters/aggregates.
3. Add the end-to-end Phase 1 integration test suite and correct PostGIS data
   population/queries.
4. Choose OUI and retention policy, then implement versioned enrichment and
   retention behavior.
5. Reassess Phase 1 exit gate before starting Phase 2 baselines.
