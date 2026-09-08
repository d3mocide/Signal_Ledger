from pathlib import Path
from app.parsers import parse

ROOT = Path(__file__).parent / "fixtures"

def accepted(source, fixture):
    records = list(parse(str(ROOT / fixture), source))
    return [record for _, record, error in records if not error], [error for _, _, error in records if error]

def test_wigle_fixture_parses_and_preserves_duplicate_for_worker_dedupe():
    rows, errors = accepted("wigle", "wigle-minimal.csv")
    assert not errors
    assert len(rows) == 3
    assert rows[0].ssid == "Authorized-AP"
    assert rows[0].latitude == 37.7749

def test_kismet_ndjson_parses_wifi_and_bluetooth():
    rows, errors = accepted("kismet", "kismet-minimal.ndjson")
    assert not errors
    assert [row.protocol for row in rows] == ["wifi", "bluetooth"]
    assert rows[0].security == "WPA3"

def test_wigle_16_metadata_row_is_skipped():
    rows, errors = accepted("wigle", "wigle-1.6-minimal.csv")
    assert not errors
    assert len(rows) == 1
    assert rows[0].security == "WPA2"

def test_parser_rejects_invalid_identifier(tmp_path):
    sample = tmp_path / "bad.csv"
    sample.write_text("MAC,FirstTime\nnot-a-mac,2026-09-07T11:00:00Z\n")
    rows = list(parse(str(sample), "wigle"))
    assert rows[0][2] == "invalid_identifier"
