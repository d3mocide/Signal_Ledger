"""Privacy-safe, explainable device similarity signals.

Fingerprints are derived from retained observations and are deliberately not
identity claims.  The public representation exposes only an opaque digest,
coarse counts, and labels for shared signal families; it never exposes a raw
address or a second address-like identifier.
"""

import hashlib
import hmac
import json
import os
import re
from collections import Counter
from datetime import datetime


FINGERPRINT_VERSION = "fingerprint-v1"
_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")


def _text(value: str | None) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).split())


def _tokens(value: str | None) -> set[str]:
    return set(_TOKEN_RE.findall(_text(value)))


def _top_values(values: list[str | None], limit: int = 8) -> set[str]:
    counts = Counter(value for value in (_text(item) for item in values) if value)
    return {value for value, _ in counts.most_common(limit)}


def signal_payload(device, observations) -> dict[str, list[str]]:
    """Build comparable, non-address signal families for one device."""
    names = []
    ssids = []
    types = []
    protocols = []
    security = []
    hours = []
    cells = []
    for observation in observations:
        names.append(observation.device_name)
        ssids.append(observation.ssid)
        types.append(observation.device_type)
        protocols.append(observation.protocol)
        security.append(observation.security)
        if observation.captured_at:
            hours.append(str(observation.captured_at.hour // 4))
        if observation.spatial_cell:
            cells.append(observation.spatial_cell)
    name_tokens = set()
    for value in names + ssids:
        name_tokens.update(_tokens(value))
    vendor = _text(device.oui_organization) if device.oui_organization != "unattributable" else ""
    return {
        "vendor": [vendor] if vendor else [],
        "protocols": sorted(_top_values(protocols)),
        "types": sorted(_top_values(types)),
        "name_tokens": sorted(name_tokens),
        "security": sorted(_top_values(security)),
        "hours": sorted(set(hours)),
        "cells": sorted(set(cells)),
    }


def opaque_fingerprint(payload: dict) -> str:
    secret = os.getenv("HMAC_SECRET", "development-only-replace-me").encode()
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hmac.new(secret, f"{FINGERPRINT_VERSION}|{canonical}".encode(), hashlib.sha256).hexdigest()
    return digest[:32]


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def similarity(left: dict, right: dict) -> tuple[float, list[str]]:
    weights = {
        "vendor": 0.25,
        "protocols": 0.18,
        "types": 0.15,
        "name_tokens": 0.18,
        "security": 0.08,
        "hours": 0.10,
        "cells": 0.06,
    }
    labels = {
        "vendor": "same vendor evidence",
        "protocols": "same radio protocol",
        "types": "same device type",
        "name_tokens": "overlapping name signals",
        "security": "same security mode",
        "hours": "same activity window",
        "cells": "overlapping coarse cells",
    }
    score = 0.0
    shared = []
    for field, weight in weights.items():
        overlap = _jaccard(set(left.get(field, [])), set(right.get(field, [])))
        score += weight * overlap
        if overlap > 0:
            shared.append(labels[field])
    return round(score, 3), shared


def public_summary(payload: dict) -> dict:
    return {
        "fingerprint_version": FINGERPRINT_VERSION,
        "fingerprint": opaque_fingerprint(payload),
        "signal_counts": {key: len(values) for key, values in payload.items()},
        "activity_windows": payload.get("hours", []),
        "coarse_cell_count": len(payload.get("cells", [])),
    }
