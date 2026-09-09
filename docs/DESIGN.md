# Signal Ledger — Design Brief

## Purpose and boundary

Signal Ledger is a private observatory for discovery logs collected in places
the operator is authorized to assess. It turns supported Wi-Fi and Bluetooth
exports into an inventory, coarse coverage view, and later a local baseline
with explainable findings.

It is deliberately **not** a radio-control, packet-capture, active-probing,
person-identification, or cross-site tracking tool. It must never retain
packet payloads, credentials, or queryable raw device addresses.

The full product requirements remain in [`../plan.md`](../plan.md). This file
records the decisions that make those requirements concrete; it should stay
short and be changed only when a decision changes.

## Users and access

The first person to open a new installation creates the initial administrator
account. Passwords are Argon2-hashed; browser sessions use opaque, HttpOnly
cookies stored server-side as token hashes. Administrators may create accounts
with these roles:

| Role | Intended access |
|---|---|
| `viewer` | Read overview, inventory, coverage, and import reports. |
| `analyst` | Viewer access plus areas, runs, and imports. |
| `auditor` | Viewer access plus audit-event review. |
| `admin` | User management and administrative recovery actions. |

For a single private operator, one administrator account is enough. The roles
exist for a future shared installation; no API keys are required for normal UI
use.

## System shape

The deployment target is intentionally a three-container Docker Compose stack:

```text
Browser
  │ authenticated HTTPS/HTTP session
  ▼
app container: React/TypeScript UI + FastAPI API + RQ worker
  ├── db container: PostgreSQL + PostGIS
  └── redis container: durable background-job queue
```

The combined app container is a deliberate MVP trade-off that keeps container
count down. The UI is React/TypeScript, built with Vite and served by FastAPI;
the backend and parser worker are Python. Redis keeps imports asynchronous.

## Data and privacy model

1. An **area** records the authorized place, authorization reference, purpose,
   and desired location precision.
2. A **run** is one collection session in an area and carries an authorization
   reference and coverage estimate.
3. An **ingestion job** stages an allowed export, records its content hash, and
   produces a versioned validation report.
4. The worker validates rows, removes within-upload duplicates, and derives a
   site-scoped HMAC token from each valid address. Full MAC addresses are not
   stored in normalized tables.
5. Only globally administered prefixes are matched to the local OUI data.
   Locally administered/randomized addresses are visibly `unattributable`.
6. Observations store source facts plus coarse spatial cells. The current UI
   uses those cells rather than precise points.

Raw uploads are currently held on the Docker named volume for reproducibility.
New uploads can receive application-level Fernet wrapping when
`RAW_STORAGE_ENCRYPTION_KEY` is configured; legacy plaintext jobs remain
readable until separately migrated or purged. The admin-reviewed retention
sweep exists, but external encrypted object storage and malware/parser
controls are still operational gates. This is a development/private-
installation boundary, not a claim of production-grade at-rest protection.

## Supported input contract today

| Source | Current supported contract |
|---|---|
| WiGLE | CSV including the common WiGLE 1.6 metadata line followed by a `MAC,...` header; timestamps, coordinates, RSSI, SSID, security fields when present. |
| Kismet | The tested CSV/JSON/NDJSON-shaped adapter contract in the parser fixtures; supported device name/type fields are retained as evidence, while real-world Kismet variants still need representative fixtures before being called supported. |

Every new real source variant gets a minimized, authorized fixture and a parser
test before it is considered supported.

## UI principles

- Overview answers “what did my last import do?” before setup actions.
- Explain terms in-place: area = authorized place/policy; run = collection
  session; import = file-validation job.
- Inventory shows pseudonymous tokens, OUI evidence, category hypothesis,
  evidence-backed device roles/context, and first/last seen—not a presumed
  person or exact device identity.
- Coverage defaults to coarse cells. A future map must preserve that default
  and make any exact-location access explicit and auditable.
- Every statistic needs a quality or coverage context; an observation count is
  not automatically a security finding.

## Decisions still required

1. Define default and maximum retention for raw logs and normalized data.
2. Decide whether exact polygon enforcement is needed for this installation.
3. Select a reviewed full IEEE OUI snapshot and update process.
4. Confirm the first real Kismet sample/version to support.
5. Before Phase 2, agree on baseline qualification thresholds and anomaly
   review/disposition vocabulary.
