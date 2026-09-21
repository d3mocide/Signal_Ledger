"""Preflight checks for uploaded capture artifacts.

These checks reject obvious source/extension mismatches before a file reaches
the worker. A deployment can route bytes to a local scanner command without
using a shell; production can require that scanner and fail closed when it is
unavailable.
"""

import csv
import io
import json
import os
from pathlib import Path
import shlex
import subprocess


TEXT_SUFFIXES = {".csv", ".json", ".ndjson"}
ALLOWED_SUFFIXES = TEXT_SUFFIXES | {".kismet"}
IDENTIFIER_HEADERS = {"mac", "mac address", "bssid", "bluetooth_address", "device"}


def _scanner_command() -> list[str]:
    try:
        return shlex.split(os.getenv("UPLOAD_SCANNER_COMMAND", ""))
    except ValueError as error:
        raise ValueError("UPLOAD_SCANNER_COMMAND is not valid shell-style command text") from error


def scan_upload(blob: bytes) -> str:
    """Pass an upload to a local scanner over stdin; never log capture bytes."""
    command = _scanner_command()
    required = os.getenv("UPLOAD_SCANNER_REQUIRED", "false").lower() == "true"
    if not command:
        if required:
            raise ValueError("Malware scanning is required but UPLOAD_SCANNER_COMMAND is not configured")
        return "not_configured"
    try:
        timeout = max(1, min(int(os.getenv("UPLOAD_SCANNER_TIMEOUT_SECONDS", "120")), 600))
    except ValueError as error:
        raise ValueError("UPLOAD_SCANNER_TIMEOUT_SECONDS must be a whole number") from error
    try:
        result = subprocess.run(
            command,
            input=blob,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError("Malware scanner could not complete") from error
    if result.returncode:
        raise ValueError("Upload was rejected by the malware scanner")
    return "clean"


def _csv_headers(text: str) -> set[str]:
    try:
        reader = csv.reader(io.StringIO(text, newline=""))
        for _, row in zip(range(50), reader):
            headers = {value.strip().lower() for value in row if value.strip()}
            if headers & IDENTIFIER_HEADERS:
                return headers
    except csv.Error as error:
        raise ValueError("CSV capture upload is malformed") from error
    raise ValueError("CSV capture upload does not contain a recognizable MAC/BSSID header")


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
        scan_upload(blob)
        return "sqlite"
    try:
        text = blob.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("Text capture uploads must be valid UTF-8") from error
    if "\x00" in text:
        raise ValueError("Text capture uploads must not contain binary NUL bytes")
    if any(ord(char) < 32 and char not in "\t\r\n" for char in text):
        raise ValueError("Text capture uploads contain unsupported control characters")
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
        scan_upload(blob)
        return "json"
    if source == "wigle":
        _csv_headers(text)
    elif suffix == ".csv":
        _csv_headers(text)
    scan_upload(blob)
    return "text"
