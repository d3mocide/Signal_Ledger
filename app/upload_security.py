"""Preflight checks for uploaded capture artifacts.

These checks reject obvious source/extension mismatches before a file reaches
the worker. They are not a malware scanner; production deployments should set
an external scanner hook and keep the roadmap gate open until its evidence is
available.
"""

import json
from pathlib import Path


TEXT_SUFFIXES = {".csv", ".json", ".ndjson"}
ALLOWED_SUFFIXES = TEXT_SUFFIXES | {".kismet"}


def validate_upload(filename: str, source: str, blob: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("Only CSV, JSON, NDJSON, and native Kismet uploads are allowed")
    if not blob:
        raise ValueError("Upload must not be empty")
    if source not in {"wigle", "kismet"}:
        raise ValueError("source_format must be wigle or kismet")
    if source == "wigle" and suffix != ".csv":
        raise ValueError("WiGLE uploads must use the CSV format")
    if source == "kismet" and suffix == ".kismet":
        if not blob[:16].startswith(b"SQLite format 3"):
            raise ValueError("Native Kismet uploads must be SQLite files")
        return "sqlite"
    try:
        text = blob.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("Text capture uploads must be valid UTF-8") from error
    if "\x00" in text:
        raise ValueError("Text capture uploads must not contain binary NUL bytes")
    stripped = text.lstrip()
    if source == "kismet" and suffix in {".json", ".ndjson"}:
        if suffix == ".json":
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as error:
                raise ValueError("Kismet JSON upload is not valid JSON") from error
            if not isinstance(parsed, (dict, list)):
                raise ValueError("Kismet JSON upload must contain an object or array")
        elif stripped:
            try:
                for line in stripped.splitlines():
                    json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError("Kismet NDJSON upload contains invalid JSON") from error
        return "json"
    if source == "wigle":
        headers = [line.strip().lower() for line in text.splitlines()[:50] if line.strip()]
        if not any(line.startswith("mac,") or ",mac," in line or line.startswith("bssid,") for line in headers):
            raise ValueError("WiGLE CSV does not contain a recognizable MAC/BSSID header")
    return "text"
