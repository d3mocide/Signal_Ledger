# Frontend and workflow review — 2026-09-09

Reviewed checkout: `3a404a0`. Scope: React frontend, supporting API contracts, design/roadmap, and all five checked-in screenshots. Application code was not changed.

Browser automation reported no available browser; localhost:8000 was unreachable from this session. Screenshot observations are from repository artifacts, not a fresh live run. Findings below are source-confirmed unless explicitly described as visual judgments or recommendations. No browser, accessibility, hardware, or production acceptance is claimed. This is a product/workflow review, not a full security audit.

### Follow-up: Playwright access restored

Later on 2026-09-09, the newly available Playwright skill successfully launched system Chromium outside the sandbox. Host-level checks confirmed the Compose app was running and localhost:8000 returned HTTP 200; the earlier connection failure was specific to the sandbox. The separate browser-connector tool still had no connected browser.

Using the user-provided test account, live login, command-center rendering, and navigation to `/#inventory` succeeded. A fresh inventory screenshot was captured at `output/playwright/live-inventory.png`. This is a limited authenticated smoke test; the full workflow and responsive/accessibility acceptance matrix below remains outstanding. Initial console errors were an unauthenticated `/v1/me` 401 and a missing favicon 404.

## Overall assessment

Signal Ledger has the right core capabilities for a private discovery-log observatory: low-friction import, pseudonymous inventory, retained evidence, coarse spatial exploration, comparison, and explicit analyst review. The dark palette, consistent panels, visible primary import action, and separation of category hypotheses from source facts are useful foundations.

The main weakness is workflow continuity. The application presents many separate destinations but does not consistently preserve what the operator is investigating or explain the next useful action. Adding more dashboards or inference features should follow repairs to status, scope, review integrity, and navigation.

The current quick-import implementation also supersedes parts of DESIGN.md: collections are optional organizational labels, while the brief still describes an area/run-first process. Align the brief, onboarding, labels, and implementation around the intended current model before expanding the UI.

## Priority findings

### 1. High — displayed import success is disconnected from job success

Evidence: `app/main.py:580–597`; `frontend/src/main.tsx:990–1030,1037,1184–1217`.

Quick import creates a run with `completed=True` before enqueueing ingestion. Capture history translates that field into “Imported”; baseline and comparison selectors also rely on it. Failed or still-running imports can therefore appear imported and become analysis candidates. Duplicate uploads return an existing job with `idempotent=True`, but the UI announces a new queued session without interpreting that flag. Polling stops after 120 attempts and clears the progress indicator without explaining that processing may continue. Only the first 20 sessions are exposed in capture history; there is no pagination or retry action despite a retry endpoint.

Recommendation: display the actual job lifecycle (uploading, queued, processing, complete, failed, already imported); admit successful sessions to analysis only after worker completion. Keep a persistent job status after navigation or reload. Add paginated/searchable history, report detail, authorized retry, and a completion action linking to that session's results. Preserve the convenient filename-based import and optional collection.

Acceptance: a deliberately failed import never reads “Imported”; duplicate upload opens its original report; a job exceeding two minutes stays visibly pending; session 21 is reachable.

### 2. High — group disposition can change more devices than the visible group

Evidence: `app/main.py:82–91,697–747`; `frontend/src/main.tsx:2724–2746`.

The queue groups devices after filtering their review status, but the PATCH endpoint reconstructs the group with status `all`. An open group of N devices may share a signature with already-dismissed or confirmed devices. “Confirm group” then updates those hidden members too. The UI does not show the expanded count or scope.

Recommendation: submit explicit selected membership or a versioned selection token and verify it server-side. Apply only to the displayed selection; make any broader action explicit. Provide group member inspection instead of only a representative record, and a clear way to revise a disposition.

Acceptance: a signature with both open and dismissed members changes only the members the operator selected, with the same displayed and audited count.

### 3. High — changing status can erase existing review context

Evidence: `frontend/src/main.tsx:2587–2592,2729–2741`; `app/main.py:740–742,928–934`.

Finding and group forms display existing notes/references as fallback values, but their mutation payloads use only local drafts and otherwise send null/empty lists. Changing a status without editing the displayed note can clear it. Group actions also apply one shared note to all members.

Recommendation: distinguish unchanged fields from explicit clearing. Preserve existing per-device context when only disposition changes; make replacing group context a separate explicit operation.

Acceptance: reopening a reviewed item and changing only status preserves its saved notes and references.

### 4. High — navigation drops investigation scope and return position

Evidence: `frontend/src/main.tsx:262–332,523–583,1449–1536,1786–1868`.

Hash routes preserve page names and device IDs, but collection/filter/page state lives in components that unmount on navigation. Category and role drilldowns pass a label without their selected collection. Vendor drilldowns can retain a previously chosen category/role. Opening evidence from review still offers “Inventory” as its back action. Global Refresh changes the workspace boundary key and remounts the active page, resetting filters and drafts.

Recommendation: encode applied collection, session, filters, sort, pagination, and return route in URL state. Restore the exact review group or inventory row on return. Refresh data without remounting the workspace. Use real links for navigable records and destinations.

Acceptance: collection-filtered category count agrees with its inventory drilldown; opening evidence and returning restores filters, page, and position; refreshing does not discard a draft.

### 5. High — exports can disagree with the table and silently stop at 5,000 rows

Evidence: `frontend/src/main.tsx:1542–1558,1588–1671`; `app/main.py:851–858`.

Inventory filter controls update draft state; the table changes only on Apply. The export URL and saved-view payload use those draft values immediately. Changing a filter and exporting without Apply can export a different population from the one shown. CSV is capped at 5,000 rows without a visible completeness notice, and it does not carry the chosen table sort. The endpoint's seven columns also omit the evidence/rule provenance advertised in README.

Recommendation: use one applied query for results, saved views, counts, and exports. State the export count and bound before downloading; support complete bounded batches or explicit partial export. Include approved rule/version and scope provenance if this is intended to be an evidence handoff.

Acceptance: exporting before Apply exports the displayed population, or explicitly prompts to apply the new filters; a population exceeding the bound cannot be mistaken for a complete export.

### 6. High — quality and coverage labels imply more certainty than the calculation supports

Evidence: `app/main.py:595`; `app/tasks.py:79,86`; `frontend/src/main.tsx:793–800,935–938`.

Quick imports set collector coverage to 1 without measurement or operator input. Observation quality is 1.0 when latitude exists and .65 otherwise; “Mean evidence quality” can consequently show 100% for data with unknown classifications and little identifying evidence. These are not independent measures of collection completeness or classification reliability.

Recommendation: show GPS completeness, parser rejection rate, observed duration, and source/protocol separately. Represent unmeasured collector coverage as unknown; label an operator estimate as an estimate. Call heuristic confidence an evidence score unless calibration supports a probability interpretation. Explain that pseudonymous records need not equal distinct physical devices, especially with randomized addresses.

Acceptance: an import with GPS but no classification evidence does not imply perfect overall evidence or full survey coverage.

### 7. Medium — comparison is useful, but currently overpromises and ends at a table

Evidence: `frontend/src/main.tsx:2857–2865`; `app/main.py:170–180,833–850`.

Selectors include all completed runs although the API requires the same collection. Defaults choose the oldest and newest entries, not necessarily a relevant pair. With exactly one run, Compare is disabled but the explanatory empty state is absent. Results have no device links or expandable before/after evidence. Coverage/duration context is absent. Both snapshots reference current Device records, so category/vendor/role comparisons cannot detect historical classification changes; observed-fact differences can still be detected. Changed devices overlap the returning count.

Recommendation: select a collection and compatible sessions, default to the latest successful session and its nearest relevant predecessor, and display source/time/GPS comparability. Use “Not observed in later session” rather than “Disappeared.” Explain the changed/returning overlap. Link each row to evidence and show actual before/after facts. Either persist classification snapshots or explicitly scope comparison to captured source facts.

Acceptance: incompatible sessions cannot be submitted; one-session guidance is visible; changed records expose the evidence difference; counts are not presented as disjoint when they overlap.

### 8. Medium — triage creates a large workload without enough decision support

Evidence: `app/main.py:75–78,99–128`; `frontend/src/main.tsx:2794–2826`; checked-in evidence-review screenshot.

All unknown categories receive priority 100. Groups with source names can correctly be considered actionable, but the card renders only rule evidence and reads latest facts from `representative.device`; the API places those facts on `representative`. This explains cards labeled actionable while saying “unknown protocol” and “No usable vendor, name, SSID, type, or rule evidence.” “Confirm group” does not explain what claim is being confirmed, and classification overrides are separate from dispositions.

Recommendation: fix the payload mapping; show the observed facts supporting priority. Distinguish “Reviewed, classification supported,” “Needs more evidence,” and “Correct category.” Prioritize within the current session by useful evidence, repeat observations, meaningful changes, and review history. Use a compact queue with an evidence detail pane and group-member access. Put no-signal material in a low-priority backlog; do not make clearing every unknown device the definition of success.

Acceptance: every actionable group states its actionable evidence; operators can tell whether a click changes classification, disposition, or a rule proposal.

### 9. Medium — command center does not answer the most immediate questions first

Evidence: `frontend/src/main.tsx:650–955`; command-center screenshot; DESIGN.md UI principles.

Lifetime counts and a very tall map precede recent imports. The attention panel counts only baseline findings; it does not summarize classification review or distinguish no evaluation from a successful evaluation with no findings. Collection and time scope are absent from the overview.

Recommendation: lead with latest import outcome, new/returning/changed records when a valid comparison exists, data limitations, and the next action. Show “No baseline evaluation yet” explicitly. Keep classification review and baseline findings as separate counts within a shared review summary. Make the map a compact secondary preview; move full exploration to Coverage.

Suggested first viewport: scope + import action; latest import result; comparison/review next steps; compact footprint and quality summary. Keep lifetime totals lower on the page.

### 10. Medium — collections combine organization with immutable ingestion policy

Evidence: `frontend/src/main.tsx:1101–1129,3134–3213`; `app/main.py:600–612`; `app/tasks.py:44–55`.

The UI calls collections optional labels, but they also carry precision/boundary policy used at ingestion. Filing afterward changes the run's collection only; it does not reapply ingestion policy or recreate unavailable addresses. A session moved into an exact collection therefore does not acquire encrypted addresses, and moving an exact capture elsewhere does not itself remove previously retained ones. “Location precision” also controls address retention, which is a different concept.

Recommendation: show collection as organizational scope and preserve the policy actually applied to each import. Distinguish location handling from address-retention settings. Explain the effect of refiling before submitting it. Use Collection and Session consistently; remove stale “Surveys” instructions and area-first onboarding. Put boundary JSON and policy controls behind an advanced section, with a preview for nontrivial boundaries.

### 11. Medium — coverage has selection limits and misleading geometry risks

Evidence: `frontend/src/main.tsx:2039–2133,2215–2230,2309–2321`; `app/main.py:874–877`.

The device picker loads only 500 devices; a device reached from inventory may not exist among its options even though the request is filtered to it. Coverage uses the top-count cell limit, which can omit sparse portions of a route. LocalMap fits longitude and latitude independently, so it does not preserve geographic aspect ratio; the cosine factor cancels in the horizontal normalization. Axis ticks span the full plot while points use an extra 22px inset, so labels and positions do not use one transform. The private SVG map provides hover titles but no selection, pan, or zoom controls.

Recommendation: use server search and an explicit selected-device chip. Disclose shown/total cells and truncation. Use a single aspect-preserving transform for points, tracks, and axes. Add a scale and an accessible cell-details table/selection. Keep local coarse mode as default and geographic mode opt-in, with a visible provider-failure fallback.

### 12. Medium — visual hierarchy and interaction semantics need a focused pass

Evidence: all five screenshots; `frontend/src/style.css`; `frontend/src/main.tsx:2780–2783`.

Visual judgment: the palette is coherent, but many operational labels are 9–11px, the inventory pushes actions to horizontal overflow, and repeated page/section introductions and permanent saved-view forms consume useful space. Fourteen navigation destinations make everyday import/review compete with advanced administration. Sidebar scrolling exists; lower destinations are not missing, but they are easy to overlook in the screenshot viewport.

Recommendation: keep the visual identity, increase key data text, reduce duplicate subtitles, place saved-view creation in a small disclosure, and offer a compact inventory column set with one Last seen column by default. Retain optional detailed columns. Make review actions and selected scope easier to distinguish.

Code-confirmed semantics: review buckets declare `tablist` but their buttons lack tab roles, selected state, panels, and arrow-key behavior. Use either a complete tabs pattern or ordinary filter buttons with pressed state. Add persistent labels to placeholder-only inputs, `aria-sort` on sortable headings, expanded state on disclosures, route focus management, inline mutation errors, and visible pending/success states. Saved-view failures are currently swallowed; a coverage save failure sets a map-notice flag instead of showing the error. Baseline/finding mutation controls are also displayed to read-only roles, although the backend rejects their requests.

The [W3C tabs pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/) specifies selected state and keyboard interaction; its [keyboard guidance](https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/) also distinguishes focus from selection. These support the semantic recommendations, not a claim that live accessibility was tested.

## Feature fit and proposed navigation

| Surface | Decision | Product reason |
| --- | --- | --- |
| Import and session history | Keep; strengthen first | This is the entry point to every useful result. |
| Inventory and device evidence | Keep as core | Primary means of exploring and checking observations. |
| Coverage | Keep as core | Explains where observations were collected; avoid implying RF coverage. |
| Run comparison | Promote in the post-import flow | Answers what changed between comparable sessions. |
| Classification review and findings | Keep separate concepts under Review | Classification uncertainty and deviations from a baseline require different decisions. |
| Categories and vendors | Make Inventory tabs/views | Helpful summaries, but not necessarily separate top-level destinations. |
| Baselines | Place under Compare as advanced | Valuable for repeated comparable routes/sites; optional for one-off exploration. |
| Rule learning and similarity | Retain as advanced evidence tools | Useful after review volume justifies them; acceptance must not imply automatic rule deployment or identity merging. |
| Collections | Keep optional and easy to reach from sessions | Organization should help retrieval/comparison without imposing setup. |
| Administration and audit | Secondary navigation | Appropriate capabilities, low daily priority for one operator. |

Suggested primary navigation: **Overview · Imports · Inventory · Coverage · Compare · Review**. Inventory contains Devices/Categories/Vendors; Compare contains Session comparison/Baselines; Review contains Classification/Findings and an advanced Rule proposals view. Collections and administration remain secondary. Preserve deep links to every existing surface.

## Intended daily workflow

1. Import a supported log; filename naming and collection assignment stay optional. Show which policy will apply.
2. Track the actual background job and open its validation report. Distinguish duplicate, failure, and successful completion.
3. Land on a session summary: accepted/rejected/duplicate rows, observed period, GPS completeness, source, record counts, and useful next actions.
4. Compare with a compatible earlier session when available; otherwise explore this session's inventory or footprint directly.
5. Open a changed or uncertain record, inspect source evidence, apply an explicit review decision, and return to the same queue position.
6. Export the applied selection with count and provenance. Optional baseline/rule work follows repeated observations and enough review evidence.

This requires shared session/collection/query state and session-filtered inventory/review endpoints where missing. It cannot be achieved solely by renaming sidebar items.

## Recommended delivery order and validation

**First: trustworthy behavior.** Repair job lifecycle, group action membership, context preservation, filter/export consistency, and quality semantics. Add targeted regression tests for those failure cases.

**Second: connected workflows.** Build the session summary, persistent route/query state, correct drilldowns, comparable-session selection, review return path, full history, and explicit partial-result notices.

**Third: presentation.** Simplify navigation, shrink the overview map, improve inventory density and review layout, and finish keyboard/responsive behavior. Split the 3,444-line main.tsx into page components and shared query/job/review utilities as these flows are changed; avoid a disconnected refactor first.

**Then: evidence-driven enhancements.** Tune triage from representative feedback, add before/after evidence snapshots if desired, improve saved-view management, and expand comparison/export only after the core loop works reliably.

Browser acceptance should cover empty workspace, one successful session, failed/duplicate/long-running imports, more than 20 sessions, a selected device outside the first 500, more than 5,000 export matches, mixed-disposition groups, back/forward/refresh, interrupted requests, and viewer/analyst/admin behavior. Test narrow and desktop layouts, 200% zoom, keyboard-only navigation, screen-reader status announcements, and offline geographic-mode recovery. Check counts against API results. A production build is a prerequisite, not proof of any of these workflows.
