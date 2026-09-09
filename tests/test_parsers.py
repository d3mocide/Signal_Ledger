from pathlib import Path
import sqlite3
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
    assert rows[0].device_name == "Kismet-fixture"
    assert rows[0].device_type == "wifi"

def test_kismet_json_array_parses():
    rows, errors = accepted("kismet", "kismet-minimal.json")
    assert not errors
    assert len(rows) == 1
    assert rows[0].protocol == "wifi"
    assert rows[0].rssi == -41

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

def test_parser_treats_null_island_and_out_of_range_coordinates_as_missing(tmp_path):
    sample = tmp_path / "placeholder-gps.csv"
    sample.write_text("MAC,FirstTime,CurrentLatitude,CurrentLongitude\n00:11:22:33:44:55,2026-09-07T11:00:00Z,0,0\n00:11:22:33:44:66,2026-09-07T11:01:00Z,99,-122\n")
    records = list(parse(str(sample), "wigle"))
    rows = [record for _, record, error in records if not error]
    assert not [error for _, _, error in records if error]
    assert [(row.latitude, row.longitude) for row in rows] == [(None, None), (None, None)]

def test_native_kismet_sqlite_reads_device_summaries_without_packet_tables(tmp_path):
    sample = tmp_path / "native.kismet"
    db = sqlite3.connect(sample)
    db.execute("CREATE TABLE devices (last_time INT, devmac TEXT, phyname TEXT, strongest_signal INT, avg_lat REAL, avg_lon REAL, type TEXT)")
    db.execute("CREATE TABLE packets (packet BLOB)")
    db.execute("INSERT INTO devices VALUES (1788897600, '00:11:22:33:44:55', 'IEEE802.11', -42, 37.1, -122.1, 'Wi-Fi AP')")
    db.execute("INSERT INTO packets VALUES (X'00112233')")
    db.commit(); db.close()
    rows = list(parse(str(sample), "kismet"))
    assert len(rows) == 1
    _, row, error = rows[0]
    assert error is None
    assert row.protocol == "wifi"
    assert row.rssi == -42
    assert row.latitude == 37.1
