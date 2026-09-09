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
- Device CSV exports are pseudonymous evidence exports. They may include site
  tokens, categories, confidence, roles, and provenance, but must not include
  raw addresses, HMAC secrets, exact coordinates, or encrypted address values.
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
- A category override creates a versioned rule proposal keyed to the retained
  vendor/name/type/SSID/protocol evidence. Proposal acceptance is a human
  review decision only; it does not automatically promote a production rule.
- Learning summaries may report dismissed reviews as a false-positive signal
  by collection and time window. This is a measurement aid, not an automatic
  threshold change.
- Device fingerprints are HMAC-derived opaque summaries of signal families
  such as vendor, protocol, type, normalized name signals, activity windows,
  security, and coarse cells. Similarity is a suggestion and never an identity
  merge.
- Run comparison uses pseudonymous device tokens within the same collection to
  show new, returning, changed, and disappeared observations. It is not a
  cross-site identity or tracking feature.
- Baseline findings are review prompts, not automated security verdicts.
  Disposition notes and up to eight evidence references are retained with the
  finding; secrets and raw addresses must never be entered there.
