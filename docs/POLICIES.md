# Signal Ledger policy defaults

These defaults apply to the private operator installation. They are reviewed
before using the system for a new authorized area.

## Retention and export

- Raw source uploads default to 30 days and normalized observations to 365 days.
- An administrator may change either window from 1 to 3,650 days in the UI.
- Retention is review-first: preview the candidate upload/run list, then type
  `PURGE` to perform the audited sweep. There is no unattended deletion timer.
- Human-readable ingestion reports contain parser counts and quality context,
  but never raw addresses, HMAC secrets, encrypted address material, or upload
  hashes. Raw source export is an administrator-controlled operational action
  outside the normal explorer UI.
- Database backups and raw-upload volume copies are separate artifacts. Both
  need the deployment's encryption-at-rest and access-control policy.
- `RAW_STORAGE_ENCRYPTION_KEY` can additionally wrap new raw uploads with
  Fernet before they are written to the raw volume. Existing plaintext jobs
  are legacy artifacts and require a separately verified migration or purge;
  this application-level option does not replace volume/object-storage
  encryption, malware scanning, or parser isolation.

## Area precision and boundaries

- Coarse cells are the default and never retain a normalized full device address.
- Exact precision is reserved for a policy-approved collection. Stored addresses
  are encrypted and can be revealed only by an administrator; each reveal is
  audited.
- An optional boundary is a GeoJSON `Polygon` with exactly one closed exterior
  ring of `[longitude, latitude]` pairs. Multipolygons and holes are not part of
  the current contract. Coordinates must be within normal WGS84 bounds.
- When a boundary is supplied, GPS-bearing observations outside it are rejected
  with the report reason `outside_area_polygon`. Observations without a valid
  GPS fix remain unlocated evidence and are not treated as in-boundary points.

## Enrichment and review

- OUI labels are evidence about a registered prefix, not a person or device
  identity. Locally administered addresses remain unattributable.
- Category hypotheses are rule-derived from retained OUI organization, device
  name/type, SSID, protocol, and privacy-safe MAC address-scope facts. Device
  names/types outrank generic vendor hints; locally administered and multicast
  addresses reduce or suppress vendor evidence. Confidence and rule evidence
  are shown with the device record.
- OUI data identifies an assigned organization, not a guaranteed product model
  or device identity. Category output remains a reviewable hypothesis.
- Device roles are a separate, multi-valued evidence layer. The current
  explainable roles are `retail_pos`, `security_access`, `smart_home`,
  `industrial_ot`, `medical`, and `guest_network`; a role may coexist with a
  device category and is never treated as proof of ownership, purpose, or
  physical location.
- Analysts may override a category; the override is durable and audited.
- Baseline findings are review prompts, not automated security verdicts.
  Disposition notes and up to eight evidence references are retained with the
  finding; secrets and raw addresses must never be entered there.
