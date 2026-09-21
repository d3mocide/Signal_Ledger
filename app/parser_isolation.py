"""Client for the optional, networkless parser-isolation service.

The service accepts one bounded capture over a Unix socket and returns framed,
normalized parser records. Raw bytes and parsed addresses never land in a shared
spool volume: the parser's only persistent mount is its socket directory.
"""

import json
import os
import socket
import struct
from datetime import datetime
from pathlib import Path
from typing import Iterator

from .parsers import ParsedObservation


MAX_FRAME_BYTES = 256 * 1024
MAX_UPLOAD_BYTES = 100 * 1024 * 1024


class ParserIsolationError(RuntimeError):
    """Raised when required isolated parsing cannot safely complete."""


def isolation_required() -> bool:
    return os.getenv("PARSER_ISOLATION_MODE", "off").lower() == "required"


def _socket_path() -> str:
    return os.getenv("PARSER_SOCKET_PATH", "/var/lib/signal-ledger/parser-socket/parser.sock")


def _timeout() -> int:
    try:
        return max(1, min(int(os.getenv("PARSER_ISOLATION_TIMEOUT_SECONDS", "120")), 600))
    except ValueError as error:
        raise ParserIsolationError("PARSER_ISOLATION_TIMEOUT_SECONDS must be a whole number") from error


def _receive_exact(connection: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = connection.recv(size - len(chunks))
        if not chunk:
            raise ParserIsolationError("Isolated parser closed its response early")
        chunks.extend(chunk)
    return bytes(chunks)


def _send_frame(connection: socket.socket, payload: bytes):
    if len(payload) > MAX_FRAME_BYTES:
        raise ParserIsolationError("Isolated parser frame exceeds the safe size limit")
    connection.sendall(struct.pack(">I", len(payload)) + payload)


def _receive_frame(connection: socket.socket) -> bytes:
    size = struct.unpack(">I", _receive_exact(connection, 4))[0]
    if not size or size > MAX_FRAME_BYTES:
        raise ParserIsolationError("Isolated parser returned an invalid frame size")
    return _receive_exact(connection, size)


def _observation(payload: dict) -> ParsedObservation:
    try:
        return ParsedObservation(
            address=str(payload["address"]),
            protocol=str(payload["protocol"]),
            captured_at=datetime.fromisoformat(str(payload["captured_at"])),
            ssid=payload.get("ssid"),
            device_name=payload.get("device_name"),
            device_type=payload.get("device_type"),
            security=payload.get("security"),
            rssi=payload.get("rssi"),
            latitude=payload.get("latitude"),
            longitude=payload.get("longitude"),
            source_row=int(payload["source_row"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ParserIsolationError("Isolated parser returned an invalid observation") from error


def isolation_healthy() -> bool:
    """Probe the local parser service without sending a capture."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(min(5, _timeout()))
            connection.connect(_socket_path())
            _send_frame(connection, b'{"operation":"ping"}')
            return json.loads(_receive_frame(connection)) == {"ready": True}
    except (OSError, json.JSONDecodeError, ParserIsolationError):
        return False


def parse_isolated(path: str, source: str) -> Iterator[tuple[int, ParsedObservation | None, str | None]]:
    """Stream a capture to the isolated service and yield validated records."""
    input_path = Path(path)
    size = input_path.stat().st_size
    if source not in {"wigle", "kismet"} or size < 1 or size > MAX_UPLOAD_BYTES:
        raise ParserIsolationError("Capture does not satisfy the isolated-parser contract")
    request = json.dumps({"source": source, "size": size}, separators=(",", ":")).encode()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(_timeout())
            connection.connect(_socket_path())
            _send_frame(connection, request)
            with input_path.open("rb") as artifact:
                while chunk := artifact.read(1024 * 1024):
                    connection.sendall(chunk)
            while True:
                payload = json.loads(_receive_frame(connection))
                if payload == {"end": True}:
                    return
                if payload.get("status") == "error":
                    raise ParserIsolationError("Isolated parser rejected the capture")
                line = int(payload["line"])
                error = payload.get("error")
                yield line, None if error else _observation(payload["observation"]), error
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        if isinstance(error, ParserIsolationError):
            raise
        raise ParserIsolationError("Isolated parser could not complete") from error
