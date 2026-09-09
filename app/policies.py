"""Small, dependency-free policy engines used during ingestion and review."""

from __future__ import annotations

from collections import defaultdict
import re
from typing import Any


CATEGORY_RULE_VERSION = "rules-v6"
ROLE_RULE_VERSION = "roles-v1"

# These are deliberately broad, explainable hints, not an identity model. OUI
# organization, device name, device type, SSID, and protocol are separate
# signals. Device name/type evidence is stronger than a generic vendor hint;
# repeated observations accumulate bounded scores in the device row.
CATEGORY_RULES = (
    {
        "category": "camera",
        "vendor": ("hikvision", "axis", "arlo", "ring", "wyze", "reolink"),
        "name": ("camera", "cctv", "doorbell", "webcam"),
        "type": ("camera", "video"),
        "ssid": ("camera", "cctv", "doorbell"),
    },
    {
        "category": "printer",
        "vendor": ("hewlett", "hp", "canon", "epson", "brother", "lexmark", "xerox"),
        "name": ("printer", "laserjet", "inkjet", "officejet", "mfc"),
        "type": ("printer", "print server"),
        "ssid": ("printer", "print", "et 2800", "ecotank"),
    },
    {
        "category": "network",
        "vendor": ("cisco", "ubiquiti", "netgear", "aruba", "tp-link", "mikrotik", "raspberry", "juniper", "fortinet", "vantiva", "commscope", "eero", "arcadyan", "zyxel", "ruckus", "extreme networks", "mojo networks", "asus", "sagemcom", "askey", "sercomm", "cradlepoint", "belkin", "mist systems", "gemtek"),
        "name": ("router", "gateway", "access point", "accesspoint", "switch", "firewall", "mesh", "unifi"),
        "type": ("access point", "wi fi ap", "wifi ap", "router", "gateway", "switch", "bridge", "firewall"),
        "ssid": ("router", "gateway", "mesh", "wifi", "access point", "accesspoint"),
    },
    {
        "category": "mobile",
        "vendor": ("apple", "samsung", "google", "xiaomi", "oneplus", "motorola", "huawei"),
        "name": ("iphone", "ipad", "android", "pixel", "galaxy", "phone", "tablet"),
        "type": ("mobile", "phone", "tablet"),
        "ssid": ("iphone", "android", "phone", "tablet", "hotspot"),
    },
    {
        "category": "workstation",
        "vendor": ("dell", "lenovo", "intel", "microsoft", "hewlett"),
        "name": ("macbook", "imac", "thinkpad", "latitude", "xps", "laptop", "desktop", "workstation", "computer"),
        "type": ("laptop", "desktop", "workstation", "computer"),
        "ssid": ("laptop", "desktop", "workstation", "computer"),
    },
    {
        "category": "audio",
        "vendor": ("sonos", "bose", "jbl", "denon", "audio"),
        "name": ("speaker", "soundbar", "airpods", "earbuds", "echo", "boss audio"),
        "type": ("speaker", "audio", "soundbar"),
        "ssid": ("speaker", "audio", "soundbar", "jbl", "boss audio"),
    },
    {
        "category": "entertainment",
        "vendor": ("roku", "lg electronics", "sony", "nintendo", "playstation"),
        "name": ("tv", "television", "roku", "fire tv", "chromecast", "console", "playstation", "xbox", "nintendo"),
        "type": ("tv", "television", "game console", "console"),
        "ssid": ("tv", "roku", "fire tv", "chromecast", "console", "playstation", "xbox"),
    },
    {
        "category": "iot",
        "vendor": ("amazon", "nest", "ecobee", "espressif", "tuya", "shelly", "home automation"),
        "name": ("sensor", "thermostat", "smart home", "smart-home", "plug", "bulb", "switchbot"),
        "type": ("sensor", "thermostat", "smart home", "appliance"),
        "ssid": ("iot", "sensor", "thermostat", "smart home", "smart-home", "plug", "bulb"),
    },
    {
        "category": "wearable",
        "vendor": ("garmin", "fitbit", "whoop", "polar", "oura", "suunto"),
        "name": ("watch", "fitbit", "garmin", "whoop", "oura", "fitness tracker"),
        "type": ("watch", "wearable", "fitness"),
        "ssid": ("watch", "wearable", "fitness"),
    },
    {
        "category": "automotive",
        "vendor": ("tesla", "harman", "continental", "bosch automotive", "denso", "delphi"),
        "name": ("vw", "volkswagen", "bmw", "audi", "porsche", "toyota", "ford", "gmc", "mygmc", "chevrolet", "mychevrolet", "ferrari", "carplay", "car cam", "car", "vehicle", "automotive", "sync", "telematics", "mmi"),
        "type": ("car", "vehicle", "automotive"),
        "ssid": ("vw", "volkswagen", "bmw", "audi", "porsche", "toyota", "ford", "gmc", "mygmc", "chevrolet", "mychevrolet", "ferrari", "carplay", "car cam", "car", "vehicle", "automotive", "telematics", "mmi"),
    },
)

# Roles are orthogonal to the device category. They describe an operational
# purpose or network context, so a device can be both ``iot`` and
# ``smart_home`` or ``network`` and ``guest_network``. These are conservative
# hints, not identity claims; every tag is backed by retained source evidence.
ROLE_RULES = (
    {
        "role": "retail_pos",
        "vendor": ("verifone", "ingenico", "ncr", "square", "clover", "toast"),
        "name": ("point of sale", "pos", "aloha", "brix", "square", "clover", "toast", "cash register", "payment terminal"),
        "type": ("point of sale", "pos", "payment terminal", "retail terminal"),
        "ssid": ("pos", "aloha", "brix", "square", "clover", "toast"),
        "threshold": .55,
    },
    {
        "role": "security_access",
        "vendor": ("alarm.com", "verkada", "avigilon", "brivo", "resideo"),
        "name": ("access control", "access-control", "keycard", "badge", "alarm", "security", "intercom", "gate", "door lock"),
        "type": ("access control", "security", "alarm", "intercom"),
        "ssid": ("access control", "access", "keycard", "badge", "alarm", "security", "intercom", "gate"),
        "threshold": .8,
    },
    {
        "role": "smart_home",
        "vendor": ("nest", "ecobee", "espressif", "tuya", "shelly", "home automation", "resideo", "gree electric"),
        "name": ("smart home", "smart-home", "home assistant", "thermostat", "smart plug", "smart bulb", "switchbot", "robot vacuum"),
        "type": ("smart home", "thermostat", "home automation", "appliance"),
        "ssid": ("smart home", "smart-home", "thermostat", "smart plug", "smart bulb", "home assistant"),
        "threshold": .8,
    },
    {
        "role": "industrial_ot",
        "vendor": ("samsara", "siemens", "schneider electric", "rockwell", "honeywell", "advantech", "moxa"),
        "name": ("plc", "scada", "modbus", "industrial", "telemetry", "telematics", "fleet"),
        "type": ("plc", "scada", "industrial", "telemetry", "telematics"),
        "ssid": ("plc", "scada", "modbus", "industrial", "telemetry", "telematics", "fleet", "samsara"),
        "threshold": .8,
    },
    {
        "role": "medical",
        "vendor": ("medtronic", "philips medical", "ge healthcare", "hillrom", "omron"),
        "name": ("medical", "health", "patient", "clinical", "vitals", "medical device"),
        "type": ("medical", "health", "patient monitor", "clinical"),
        "ssid": ("medical", "health", "patient", "clinical", "hospital"),
        "threshold": .8,
    },
    {
        "role": "guest_network",
        "vendor": (),
        "name": (),
        "type": (),
        "ssid": ("guest", "visitor", "public", "byod", "eduroam"),
        "threshold": .55,
    },
)

DEVICE_ROLE_NAMES = tuple(rule["role"] for rule in ROLE_RULES)


def _signal_text(value: str | None) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).split())


def _match_term(text: str, terms: tuple[str, ...]) -> str | None:
    tokens = text.split()
    for term in terms:
        normalized = _signal_text(term)
        if not normalized:
            continue
        if f" {normalized} " in f" {text} ":
            return term
        compact = normalized.replace(" ", "")
        if " " not in normalized and any(token.startswith(compact) and len(token) > len(compact) and token[len(compact):].isdigit() for token in tokens):
            return term
    return None


def mac_address_scope(address: str | None) -> str:
    """Return privacy-safe MAC metadata without retaining the address."""
    compact = re.sub(r"[:-]", "", address or "")
    if len(compact) != 12 or not re.fullmatch(r"[0-9a-fA-F]{12}", compact):
        return "unknown"
    first_octet = int(compact[:2], 16)
    if first_octet & 1:
        return "multicast"
    if first_octet & 2:
        return "locally_administered"
    return "globally_administered"


def category_scores(
    vendor: str | None,
    ssid: str | None,
    protocol: str | None,
    device_name: str | None = None,
    device_type: str | None = None,
    address_scope: str | None = None,
) -> tuple[dict[str, float], list[str]]:
    vendor_text = _signal_text(vendor)
    ssid_text = _signal_text(ssid)
    name_text = _signal_text(device_name)
    type_text = _signal_text(device_type)
    scores: dict[str, float] = defaultdict(float)
    evidence: list[str] = []
    vendor_weight = .18 if address_scope == "locally_administered" else .72
    for rule in CATEGORY_RULES:
        category = rule["category"]
        vendor_match = _match_term(vendor_text, rule["vendor"])
        name_match = _match_term(name_text, rule["name"])
        type_match = _match_term(type_text, rule["type"])
        ssid_match = _match_term(ssid_text, rule["ssid"])
        if vendor_match:
            scores[category] += vendor_weight
            evidence.append(f"{category}: vendor contains '{vendor_match}'")
        if name_match:
            scores[category] += 1.0
            evidence.append(f"{category}: device name contains '{name_match}'")
        if type_match:
            scores[category] += .85
            evidence.append(f"{category}: device type contains '{type_match}'")
        if ssid_match:
            scores[category] += .55
            evidence.append(f"{category}: SSID contains '{ssid_match}'")
    if protocol == "bluetooth":
        scores["bluetooth"] += .45
        evidence.append("bluetooth: protocol is bluetooth")
    if address_scope == "locally_administered":
        evidence.append("address: locally administered; OUI evidence is low confidence")
    elif address_scope == "multicast":
        evidence.append("address: multicast/group address; not a device vendor signal")
    return {key: round(min(value, 5.0), 3) for key, value in scores.items()}, evidence


def category_from_scores(scores: dict[str, float], evidence: list[str] | None = None) -> tuple[str, float, list[str]]:
    if not scores:
        return "unknown", 0.0, ["unknown: no configured category rule matched"]
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    category, top_score = ordered[0]
    runner_up = ordered[1][1] if len(ordered) > 1 else 0.0
    if top_score < .45:
        return "unknown", 0.0, (evidence or ["unknown: category evidence below threshold"])[:12]
    confidence = min(.98, .45 + min(.3, top_score * .12) + min(.2, max(0.0, top_score - runner_up) * .14))
    return category, round(confidence, 3), (evidence or [])[:12]


def device_role_scores(
    vendor: str | None,
    ssid: str | None,
    protocol: str | None,
    device_name: str | None = None,
    device_type: str | None = None,
) -> tuple[dict[str, float], list[str]]:
    """Score explainable operational roles without making an identity claim."""
    vendor_text = _signal_text(vendor)
    ssid_text = _signal_text(ssid)
    name_text = _signal_text(device_name)
    type_text = _signal_text(device_type)
    scores: dict[str, float] = defaultdict(float)
    evidence: list[str] = []
    for rule in ROLE_RULES:
        role = rule["role"]
        vendor_match = _match_term(vendor_text, rule["vendor"])
        name_match = _match_term(name_text, rule["name"])
        type_match = _match_term(type_text, rule["type"])
        ssid_match = _match_term(ssid_text, rule["ssid"])
        if vendor_match:
            scores[role] += .65
            evidence.append(f"{role}: vendor contains '{vendor_match}'")
        if name_match:
            scores[role] += 1.0
            evidence.append(f"{role}: device name contains '{name_match}'")
        if type_match:
            scores[role] += .85
            evidence.append(f"{role}: device type contains '{type_match}'")
        if ssid_match:
            scores[role] += .55
            evidence.append(f"{role}: SSID contains '{ssid_match}'")
    return {key: round(min(value, 5.0), 3) for key, value in scores.items()}, evidence


def device_roles_from_scores(scores: dict[str, float]) -> list[str]:
    thresholds = {rule["role"]: rule["threshold"] for rule in ROLE_RULES}
    return [
        role for role, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        if score >= thresholds.get(role, 1.0)
    ][:6]


def validate_polygon(value: Any) -> dict | None:
    """Validate the deliberately small GeoJSON Polygon contract.

    Signal Ledger accepts one exterior ring only.  Holes and multipolygons are
    rejected until there is a reviewable UI for them, which keeps the exact
    location boundary easy to explain and test.
    """
    if value is None:
        return None
    if not isinstance(value, dict) or value.get("type") != "Polygon":
        raise ValueError("polygon must be a GeoJSON Polygon")
    coordinates = value.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) != 1:
        raise ValueError("polygon must contain exactly one exterior ring")
    ring = coordinates[0]
    if not isinstance(ring, list) or len(ring) < 4 or ring[0] != ring[-1]:
        raise ValueError("polygon exterior ring must contain at least four closed points")
    normalized: list[list[float]] = []
    for point in ring:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError("polygon coordinates must be [longitude, latitude]")
        lon, lat = point
        if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
            raise ValueError("polygon coordinates must be numeric")
        if not -180 <= lon <= 180 or not -90 <= lat <= 90:
            raise ValueError("polygon coordinates are outside valid latitude/longitude bounds")
        normalized.append([float(lon), float(lat)])
    return {"type": "Polygon", "coordinates": [normalized]}


def point_in_polygon(latitude: float | None, longitude: float | None, polygon: dict | None) -> bool:
    """Return whether a point is inside the validated polygon exterior ring."""
    if latitude is None or longitude is None or not polygon:
        return True
    ring = polygon["coordinates"][0]
    inside = False
    for index, (x1, y1) in enumerate(ring):
        x2, y2 = ring[(index + 1) % len(ring)]
        crosses = (y1 > latitude) != (y2 > latitude)
        if crosses:
            intersection = (x2 - x1) * (latitude - y1) / ((y2 - y1) or 1e-12) + x1
            if longitude < intersection:
                inside = not inside
    return inside


def classify_device(
    vendor: str | None,
    ssid: str | None,
    protocol: str | None,
    device_name: str | None = None,
    device_type: str | None = None,
    address_scope: str | None = None,
) -> tuple[str, float, list[str]]:
    """Classify only from retained source facts, returning scored evidence."""
    scores, evidence = category_scores(vendor, ssid, protocol, device_name, device_type, address_scope)
    return category_from_scores(scores, evidence)
