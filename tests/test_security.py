import multiprocessing
import time

import pytest

from app.parser_isolation import ParserIsolationError, isolation_healthy, isolation_required, parse_isolated
from app.parser_worker import serve
from app.security import password_hash, password_valid, token_hash

def test_password_is_argon2_hashed_and_verifiable():
    encoded = password_hash("a-long-enough-test-password")
    assert encoded.startswith("$argon2")
    assert password_valid("a-long-enough-test-password", encoded)
    assert not password_valid("wrong-password-value", encoded)

def test_session_token_hash_is_stable_and_not_plaintext():
    assert token_hash("example") == token_hash("example")
    assert token_hash("example") != "example"


def test_required_parser_isolation_fails_closed_without_the_service(tmp_path, monkeypatch):
    capture = tmp_path / "capture.csv"
    capture.write_text("MAC,FirstTime\n00:11:22:33:44:55,2026-09-08T12:00:00Z\n")
    monkeypatch.setenv("PARSER_ISOLATION_MODE", "required")
    monkeypatch.setenv("PARSER_SOCKET_PATH", str(tmp_path / "absent.sock"))
    assert isolation_required()
    with pytest.raises(ParserIsolationError, match="could not complete"):
        list(parse_isolated(str(capture), "wigle"))


def test_isolated_parser_streams_validated_records_without_raw_spool(tmp_path, monkeypatch):
    socket_path = tmp_path / "parser.sock"
    capture = tmp_path / "capture.csv"
    capture.write_text("MAC,FirstTime,SSID\n00:11:22:33:44:55,2026-09-08T12:00:00Z,isolated-fixture\n")
    monkeypatch.setenv("PARSER_SOCKET_PATH", str(socket_path))
    process = multiprocessing.Process(target=serve)
    process.start()
    try:
        for _ in range(50):
            if socket_path.exists():
                break
            time.sleep(.02)
        else:
            raise AssertionError("isolated parser did not create its Unix socket")
        assert isolation_healthy()
        records = list(parse_isolated(str(capture), "wigle"))
        assert records[0][2] is None
        assert records[0][1].ssid == "isolated-fixture"
        assert list(tmp_path.glob("capture-*")) == []
    finally:
        process.terminate()
        process.join(timeout=3)
