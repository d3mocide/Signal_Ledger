"""Versioned, deliberately narrow adapters for Phase 1 source fixtures."""
import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

MAC = re.compile(r"^[0-9A-Fa-f]{2}[:-]([0-9A-Fa-f]{2}[:-]){4}[0-9A-Fa-f]{2}$")
PARSER_VERSION = "phase1.2"

@dataclass(frozen=True)
class ParsedObservation:
    address: str
    protocol: str
    captured_at: datetime
    ssid: str | None
    security: str | None
    rssi: float | None
    latitude: float | None
    longitude: float | None
    source_row: int

def field(row, *names):
    lowered = {str(k).lower().strip(): v for k, v in row.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value not in (None, ""): return str(value).strip()
    return None

def as_dt(value):
    if not value: return None
    try: return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        try: return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError: return None

def as_number(value):
    try: return float(value) if value not in (None, "") else None
    except ValueError: return None

def source_rows(path: str, source: str):
    text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    if source == "kismet" and text.lstrip().startswith(("{", "[")):
        return json.loads(text) if text.lstrip().startswith("[") else [json.loads(x) for x in text.splitlines() if x.strip()]
    lines = text.splitlines()
    # WiGLE 1.6 exports start with a provenance metadata row, followed by the
    # actual CSV header.  Treat it as provenance, never as a record.
    if source == "wigle":
        for index, line in enumerate(lines):
            if line.strip().lower().startswith("mac,"):
                lines = lines[index:]
                break
    return list(csv.DictReader(lines))

def parse(path: str, source: str):
    for line, row in enumerate(source_rows(path, source), start=2):
        address = field(row, "bssid", "mac", "mac address", "bluetooth_address", "device")
        protocol = field(row, "protocol", "type") or ("bluetooth" if field(row, "bluetooth_address") else "wifi")
        protocol = "bluetooth" if protocol.lower() in ("bluetooth", "ble", "classic") else "wifi"
        captured = as_dt(field(row, "captured_at", "time", "timestamp", "firsttime", "firstseen", "lasttime", "time_sec"))
        if not MAC.match(address or ""): yield line, None, "invalid_identifier"; continue
        if not captured: yield line, None, "invalid_timestamp"; continue
        yield line, ParsedObservation(address, protocol, captured, field(row, "ssid", "name"), field(row, "security", "encryption", "authmode"), as_number(field(row, "rssi", "signal")), as_number(field(row, "lat", "latitude", "currentlatitude")), as_number(field(row, "lon", "longitude", "currentlongitude")), line), None
