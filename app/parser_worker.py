"""Networkless parser service used by the optional hardened Compose profile."""

import json
import os
import resource
import socket
import struct
import tempfile
from pathlib import Path

from .parser_isolation import MAX_FRAME_BYTES, MAX_UPLOAD_BYTES
from .parsers import parse


def _integer(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(int(os.getenv(name, str(default))), maximum))
    except ValueError:
        return default


def _set_limits():
    memory = _integer("PARSER_MAX_MEMORY_MB", 512, 128, 2048) * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    resource.setrlimit(resource.RLIMIT_CPU, (_integer("PARSER_MAX_CPU_SECONDS", 90, 5, 600),) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_UPLOAD_BYTES + MAX_FRAME_BYTES,) * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def _receive_exact(connection: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = connection.recv(size - len(chunks))
        if not chunk:
            raise ValueError("client closed request early")
        chunks.extend(chunk)
    return bytes(chunks)


def _receive_frame(connection: socket.socket) -> bytes:
    size = struct.unpack(">I", _receive_exact(connection, 4))[0]
    if not size or size > MAX_FRAME_BYTES:
        raise ValueError("invalid request frame")
    return _receive_exact(connection, size)


def _send(connection: socket.socket, payload: dict):
    encoded = json.dumps(payload, separators=(",", ":")).encode()
    if len(encoded) > MAX_FRAME_BYTES:
        raise ValueError("normalized record exceeds output limit")
    connection.sendall(struct.pack(">I", len(encoded)) + encoded)


def _observation_payload(observation) -> dict:
    return {
        "address": observation.address,
        "protocol": observation.protocol,
        "captured_at": observation.captured_at.isoformat(),
        "ssid": observation.ssid,
        "device_name": observation.device_name,
        "device_type": observation.device_type,
        "security": observation.security,
        "rssi": observation.rssi,
        "latitude": observation.latitude,
        "longitude": observation.longitude,
        "source_row": observation.source_row,
    }


def _receive_capture(connection: socket.socket, size: int) -> str:
    temporary = tempfile.NamedTemporaryFile(prefix="capture-", suffix=".artifact", dir="/tmp", delete=False)
    try:
        remaining = size
        while remaining:
            chunk = _receive_exact(connection, min(1024 * 1024, remaining))
            temporary.write(chunk)
            remaining -= len(chunk)
        temporary.close()
        return temporary.name
    except Exception:
        temporary.close()
        Path(temporary.name).unlink(missing_ok=True)
        raise


def _handle(connection: socket.socket):
    artifact = None
    try:
        request = json.loads(_receive_frame(connection))
        if request == {"operation": "ping"}:
            _send(connection, {"ready": True})
            return
        source, size = request.get("source"), request.get("size")
        if source not in {"wigle", "kismet"} or not isinstance(size, int) or not 0 < size <= MAX_UPLOAD_BYTES:
            raise ValueError("invalid parse request")
        artifact = _receive_capture(connection, size)
        for line, observation, error in parse(artifact, source):
            _send(connection, {"line": line, "error": error} if error else {"line": line, "observation": _observation_payload(observation)})
        _send(connection, {"end": True})
    except Exception:
        try:
            _send(connection, {"status": "error"})
        except OSError:
            pass
    finally:
        if artifact:
            Path(artifact).unlink(missing_ok=True)
        connection.close()


def serve():
    _set_limits()
    socket_path = Path(os.getenv("PARSER_SOCKET_PATH", "/var/lib/signal-ledger/parser-socket/parser.sock"))
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    socket_path.unlink(missing_ok=True)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(socket_path))
        os.chmod(socket_path, 0o660)
        listener.listen(8)
        while True:
            connection, _ = listener.accept()
            _handle(connection)


if __name__ == "__main__":
    serve()
