"""Local OUI catalog parsing and deterministic, privacy-safe resolution."""

import csv
import io
import re
from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import OUIAssignment, OUIMasterAssignment

VALID_PREFIX_LENGTHS = {6, 7, 9}
MASTER_CATALOG = "oui-master"
IEEE_CATALOG = "ieee-ma-l"


def normalize_prefix(value: object) -> str | None:
    """Return a 24-, 28-, or 36-bit assignment in compact uppercase form."""
    prefix = re.sub(r"[^0-9A-Fa-f]", "", str(value or "")).upper()
    return prefix if len(prefix) in VALID_PREFIX_LENGTHS and re.fullmatch(r"[0-9A-F]+", prefix) else None


def bounded_text(value: object, limit: int) -> str | None:
    value = str(value or "").strip()
    return value[:limit] or None


def parse_sources(value: object) -> list[str]:
    if isinstance(value, list):
        values = value
    else:
        values = re.split(r"[+,;]", str(value or ""))
    return list(dict.fromkeys(item[:40] for item in (str(x).strip() for x in values) if item))[:8]


def parse_oui_master_csv(blob: bytes) -> dict[str, dict]:
    """Parse the documented master_oui.csv contract without retaining raw MACs."""
    try:
        rows = csv.DictReader(io.StringIO(blob.decode("utf-8-sig", errors="strict")))
        if not rows.fieldnames or not {"oui", "manufacturer"}.issubset({name.strip().lower() for name in rows.fieldnames if name}):
            raise ValueError("missing oui/manufacturer headers")
        assignments: dict[str, dict] = {}
        for row in rows:
            normalized_row = {(key or "").strip().lower(): value for key, value in row.items()}
            prefix = normalize_prefix(normalized_row.get("oui"))
            organization = bounded_text(normalized_row.get("manufacturer"), 255)
            if not prefix or not organization:
                continue
            assignments[prefix] = {
                "prefix": prefix,
                "organization": organization,
                "registry": bounded_text(normalized_row.get("registry"), 24),
                "short_name": bounded_text(normalized_row.get("short_name"), 120),
                "device_type": bounded_text(normalized_row.get("device_type"), 80),
                "registered_date": bounded_text(normalized_row.get("registered_date"), 32),
                "organization_address": bounded_text(normalized_row.get("address"), 600),
                "country": bounded_text(normalized_row.get("country"), 8),
                "sources": parse_sources(normalized_row.get("sources")),
            }
    except (csv.Error, UnicodeDecodeError, ValueError) as error:
        raise ValueError("Invalid OUI Master CSV: " + str(error)) from error
    if len(assignments) < 100:
        raise ValueError("CSV does not look like an OUI Master catalog")
    return assignments


def load_catalog(db: Session) -> dict[str, dict]:
    """Resolve longest matching prefix; official IEEE wins equal 24-bit conflicts."""
    catalog: dict[str, dict] = {}
    for assignment in db.scalars(select(OUIMasterAssignment)).all():
        catalog[assignment.prefix] = {
            "prefix": assignment.prefix, "organization": assignment.organization,
            "registry": assignment.registry, "short_name": assignment.short_name,
            "device_type": assignment.device_type, "sources": assignment.sources or [],
            "catalog": MASTER_CATALOG,
        }
    # Apply IEEE last: it deliberately takes precedence only for the same MA-L prefix.
    for assignment in db.scalars(select(OUIAssignment)).all():
        catalog[assignment.prefix] = {
            "prefix": assignment.prefix, "organization": assignment.organization,
            "registry": "MA-L", "short_name": None, "device_type": None,
            "sources": ["IEEE"], "catalog": IEEE_CATALOG,
        }
    return catalog


def lookup(catalog: Mapping[str, dict], normalized_address: str | None) -> dict | None:
    compact = re.sub(r"[^0-9A-Fa-f]", "", normalized_address or "").upper()
    if not re.fullmatch(r"[0-9A-F]{12}", compact):
        return None
    for length in (9, 7, 6):
        result = catalog.get(compact[:length])
        if result:
            return result
    return None


def lookup_stored_prefix(catalog: Mapping[str, dict], prefix: str | None) -> dict | None:
    """Re-enrich legacy records without ever needing their discarded MAC address."""
    normalized = normalize_prefix(prefix)
    return catalog.get(normalized) if normalized else None


def apply_match(device, match: dict | None) -> None:
    if not match:
        device.oui_organization = "unattributable"
        device.oui_registry = None
        device.oui_sources = []
        device.oui_device_type = None
        device.oui_catalog = None
        return
    device.oui_prefix = match["prefix"]
    device.oui_organization = match["organization"]
    device.oui_registry = match.get("registry")
    device.oui_sources = match.get("sources") or []
    # This upstream field is an explicitly displayed heuristic, never a category override.
    device.oui_device_type = match.get("device_type")
    device.oui_catalog = match.get("catalog")
