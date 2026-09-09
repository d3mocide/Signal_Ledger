import asyncio
from datetime import datetime
from io import BytesIO

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql.elements import TextClause
from starlette.datastructures import UploadFile

import app.main as main_module
import app.tasks as tasks_module
from app.crypto import decrypt_address
from app.database import Base
from app.main import AnomalyPatch, AreaInput, AreaPatch, BaselineInput, HTTPException, RetentionSweepInput, create_area, create_baseline, delete_area, device_detail, device_vendor_summary, devices, dump, import_oui, list_anomalies, list_areas, list_runs, map_clusters, map_track, purge_retention, purge_run_data, quick_import, refresh_oui, rename_area, retention_preview, reveal_device_address, update_anomaly
from app.models import Device, IngestionJob, Observation, SurveyArea, SurveyRun
from app.security import Principal
from app.tasks import process_ingestion


def test_inventory_detail_and_coarse_map_filters_work_together():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    area = SurveyArea(name="Authorized test area", authorization_ref="AUTH-1", precision="coarse")
    db.add(area); db.flush()
    first_run = SurveyRun(survey_area_id=area.id, name="Morning", authorization_ref="AUTH-1", collector_coverage=.9)
    second_run = SurveyRun(survey_area_id=area.id, name="Evening", authorization_ref="AUTH-1", collector_coverage=.8)
    db.add_all([first_run, second_run]); db.flush()
    first_device = Device(survey_area_id=area.id, token="a" * 64, oui_prefix="001122", oui_organization="Example OUI", first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 2))
    second_device = Device(survey_area_id=area.id, token="b" * 64, oui_organization="unattributable", first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1))
    db.add_all([first_device, second_device]); db.flush()
    db.add_all([
        Observation(survey_run_id=first_run.id, ingestion_job_id=1, device_id=first_device.id, captured_at=datetime(2026, 1, 1, 10), protocol="wifi", ssid="test", security="WPA2", rssi=-50, latitude=1, longitude=2, spatial_cell="1.000,2.000", quality=1, source_row=2),
        Observation(survey_run_id=second_run.id, ingestion_job_id=1, device_id=first_device.id, captured_at=datetime(2026, 1, 2, 10), protocol="wifi", ssid="test-5g", security="WPA2", rssi=-55, latitude=1.001, longitude=2.001, spatial_cell="1.001,2.001", quality=1, source_row=3),
        Observation(survey_run_id=first_run.id, ingestion_job_id=1, device_id=second_device.id, captured_at=datetime(2026, 1, 1, 11), protocol="wifi", ssid=None, security=None, rssi=-65, latitude=1, longitude=2, spatial_cell="1.000,2.000", quality=1, source_row=4),
    ])
    db.commit()
    viewer = Principal(1, "tester", "viewer")

    inventory = devices(area_id=area.id, limit=1, offset=0, db=db, principal=viewer)
    assert inventory["total"] == 2
    assert len(inventory["items"]) == 1
    assert inventory["items"][0]["last_ssid"] == "test-5g"
    assert inventory["items"][0]["last_protocol"] == "wifi"

    attributed = devices(area_id=area.id, attributed_only=True, limit=100, offset=0, db=db, principal=viewer)
    assert attributed["total"] == 1
    assert attributed["items"][0]["oui_organization"] == "Example OUI"

    sorted_by_vendor = devices(area_id=area.id, sort="oui_organization", direction="asc", limit=100, offset=0, db=db, principal=viewer)
    orgs = [item["oui_organization"] for item in sorted_by_vendor["items"]]
    assert orgs == sorted(orgs, key=str.lower)

    detail = device_detail(first_device.id, limit=100, db=db, principal=viewer)
    assert detail["summary"] == {"observations": 2, "runs": 2, "coarse_cells": 2}
    assert {item["run_name"] for item in detail["observations"]} == {"Morning", "Evening"}

    mapped = map_clusters(run_id=first_run.id, device_id=first_device.id, limit=1000, db=db, principal=viewer)
    assert mapped == [{"cell": "1.000,2.000", "count": 1, "avg_rssi": -50.0, "device_count": 1}]


def test_map_clusters_excludes_stored_null_island_placeholder_coordinates():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    area = SurveyArea(name="Map area", authorization_ref="AUTH-map", precision="coarse")
    db.add(area); db.flush()
    run = SurveyRun(survey_area_id=area.id, name="Map run", authorization_ref="AUTH-map")
    device = Device(survey_area_id=area.id, token="m" * 64, oui_organization="unattributable", first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1))
    db.add_all([run, device]); db.flush()
    db.add_all([
        Observation(survey_run_id=run.id, ingestion_job_id=1, device_id=device.id, captured_at=datetime(2026, 1, 1), protocol="wifi", latitude=0, longitude=0, spatial_cell="0.000,0.000", quality=1, source_row=1),
        Observation(survey_run_id=run.id, ingestion_job_id=1, device_id=device.id, captured_at=datetime(2026, 1, 1), protocol="wifi", latitude=45.5, longitude=-122.6, spatial_cell="45.500,-122.600", quality=1, source_row=2),
    ])
    db.commit()
    assert map_clusters(run_id=run.id, limit=1000, db=db, principal=Principal(1, "viewer", "viewer")) == [{"cell": "45.500,-122.600", "count": 1, "avg_rssi": None, "device_count": 1}]
    assert map_track(run_id=run.id, limit=100, db=db, principal=Principal(1, "viewer", "viewer")) == {"segments": [[{"cell": "45.500,-122.600", "captured_at": datetime(2026, 1, 1)}]], "truncated": False}


def test_frozen_baseline_flags_later_novel_device():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    area = SurveyArea(name="Baseline area", authorization_ref="AUTH-2", precision="coarse")
    db.add(area); db.flush()
    training = SurveyRun(survey_area_id=area.id, name="Training", authorization_ref="AUTH-2", collector_coverage=1, completed=True)
    later = SurveyRun(survey_area_id=area.id, name="Later", authorization_ref="AUTH-2", collector_coverage=1, completed=True)
    db.add_all([training, later]); db.flush()
    # Matches real ingestion: Device.survey_area_id is never populated, so the
    # baseline/anomaly path must scope by run, not by this column.
    known = Device(token="c" * 64, oui_organization="Example OUI", first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1))
    novel = Device(token="d" * 64, oui_organization="New OUI", first_seen=datetime(2026, 1, 2), last_seen=datetime(2026, 1, 2))
    db.add_all([known, novel]); db.flush()
    db.add_all([
        Observation(survey_run_id=training.id, ingestion_job_id=1, device_id=known.id, captured_at=datetime(2026, 1, 1, 9), protocol="wifi", ssid="known", security="WPA2", rssi=-50, latitude=1, longitude=2, spatial_cell="1.000,2.000", quality=1, source_row=1),
        Observation(survey_run_id=later.id, ingestion_job_id=2, device_id=novel.id, captured_at=datetime(2026, 1, 2, 9), protocol="wifi", ssid="novel", security="WPA2", rssi=-50, latitude=1, longitude=2, spatial_cell="1.000,2.000", quality=1, source_row=1),
    ])
    db.commit()
    analyst = Principal(1, "analyst", "analyst")
    baseline = create_baseline(BaselineInput(survey_area_id=area.id, name="First baseline", run_ids=[training.id]), db=db, principal=analyst)
    findings = list_anomalies(baseline_id=baseline["id"], db=db, principal=analyst)
    assert {item["kind"] for item in findings} == {"novel_device", "novel_vendor"}
    reviewed = update_anomaly(findings[0]["id"], AnomalyPatch(status="confirmed", disposition_note="Reviewed against approved change request."), db=db, principal=analyst)
    assert reviewed["status"] == "confirmed"
    assert reviewed["disposition_note"] == "Reviewed against approved change request."


def test_oui_csv_import_reenriches_existing_prefixes():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    area = SurveyArea(name="OUI area", authorization_ref="AUTH-3", precision="coarse")
    db.add(area); db.flush()
    device = Device(survey_area_id=area.id, token="e" * 64, oui_prefix="001122", oui_organization="unattributable", first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1))
    db.add(device); db.commit()
    registry = ("Registry,Assignment,Organization Name\nMA-L,001122,Example Network Works\n" + "".join(f"MA-L,{index:06X},Vendor {index}\n" for index in range(100, 200))).encode()
    upload = UploadFile(filename="ieee.csv", file=BytesIO(registry))
    result = asyncio.run(import_oui(upload, db=db, principal=Principal(1, "admin", "admin")))
    assert result["assignments"] == 101
    assert db.get(Device, device.id).oui_organization == "Example Network Works"


def test_oui_refresh_fetches_and_applies_the_ieee_registry(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    area = SurveyArea(name="OUI refresh area", authorization_ref="AUTH-5", precision="coarse")
    db.add(area); db.flush()
    device = Device(survey_area_id=area.id, token="f" * 64, oui_prefix="001122", oui_organization="unattributable", first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1))
    db.add(device); db.commit()
    registry = ("Registry,Assignment,Organization Name\nMA-L,001122,Example Network Works\n" + "".join(f"MA-L,{index:06X},Vendor {index}\n" for index in range(100, 200))).encode()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, limit=-1):
            return registry

    monkeypatch.setattr(main_module.urllib.request, "urlopen", lambda request, timeout=None: FakeResponse())
    admin = Principal(1, "admin", "admin")
    result = refresh_oui(db=db, principal=admin)
    assert result["assignments"] == 101
    assert db.get(Device, device.id).oui_organization == "Example Network Works"

    again = refresh_oui(db=db, principal=admin)
    assert again["idempotent"] is True


def test_oui_refresh_surfaces_a_clear_error_when_ieee_is_unreachable(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    def unreachable(request, timeout=None):
        raise main_module.urllib.error.URLError("network is unreachable")

    monkeypatch.setattr(main_module.urllib.request, "urlopen", unreachable)
    with pytest.raises(HTTPException) as excinfo:
        refresh_oui(db=db, principal=Principal(1, "admin", "admin"))
    assert excinfo.value.status_code == 502


def test_direct_import_creates_a_filename_named_session_and_default_collection(tmp_path, monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    monkeypatch.setattr(main_module, "RAW", tmp_path)
    monkeypatch.setattr(main_module.queue, "enqueue", lambda *args, **kwargs: None)
    upload = UploadFile(filename="phone-capture.csv", file=BytesIO(b"MAC,FirstTime\n00:11:22:33:44:55,2026-09-08T12:00:00Z\n"))
    result = asyncio.run(quick_import(source_format="wigle", file=upload, session_name=None, collection_name=None, db=db, principal=Principal(1, "analyst", "analyst")))
    assert result["filename"] == "phone-capture.csv"
    run = db.scalar(select(SurveyRun))
    assert run.survey_area_id is None
    assert run.name.startswith("phone-capture · ")
    assert run.completed


def test_retention_preview_is_non_destructive_and_confirmed_sweep_removes_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("RAW_RETENTION_DAYS", "30")
    monkeypatch.setenv("NORMALIZED_RETENTION_DAYS", "365")
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    area = SurveyArea(name="Retention area", authorization_ref="AUTH-4", precision="coarse")
    db.add(area); db.flush()
    old_run = SurveyRun(survey_area_id=area.id, name="Old evidence", authorization_ref="AUTH-4", created_at=datetime(2024, 1, 1))
    current_run = SurveyRun(survey_area_id=area.id, name="Current evidence", authorization_ref="AUTH-4", created_at=datetime(2026, 9, 1))
    db.add_all([old_run, current_run]); db.flush()
    old_raw, current_raw = tmp_path / "old.csv", tmp_path / "current.csv"
    old_raw.write_text("old"); current_raw.write_text("current")
    old_job = IngestionJob(survey_run_id=old_run.id, filename="old.csv", source_format="wigle", file_hash="1" * 64, raw_path=str(old_raw), created_at=datetime(2024, 1, 1))
    current_job = IngestionJob(survey_run_id=current_run.id, filename="current.csv", source_format="wigle", file_hash="2" * 64, raw_path=str(current_raw), created_at=datetime(2024, 1, 1))
    device = Device(survey_area_id=area.id, token="f" * 64, oui_organization="unattributable", first_seen=datetime(2024, 1, 1), last_seen=datetime(2024, 1, 1))
    db.add_all([old_job, current_job, device]); db.flush()
    db.add(Observation(survey_run_id=old_run.id, ingestion_job_id=old_job.id, device_id=device.id, captured_at=datetime(2024, 1, 1), protocol="wifi", quality=1, source_row=1))
    db.commit()
    admin = Principal(1, "admin", "admin")

    preview = retention_preview(db)
    assert {item["id"] for item in preview["survey_runs"]} == {old_run.id}
    assert current_raw.exists() and old_raw.exists()
    result = purge_retention(RetentionSweepInput(confirm="PURGE"), db=db, principal=admin)
    assert result["purged_survey_runs"] == [old_run.id]
    assert db.get(SurveyRun, old_run.id) is None
    assert db.get(SurveyRun, current_run.id) is not None
    assert db.get(IngestionJob, current_job.id).raw_path == "expired"
    assert not old_raw.exists() and not current_raw.exists()


class _PostgisAgnosticSession(Session):
    """process_ingestion's PostGIS geometry backfill has no sqlite equivalent;
    this lets tests exercise the rest of the pipeline against sqlite without
    standing up real PostGIS, per the still-open integration-test roadmap item."""

    def execute(self, statement, *args, **kwargs):
        if isinstance(statement, TextClause) and "ST_MakePoint" in statement.text:
            return super().execute(text("SELECT 1"))
        return super().execute(statement, *args, **kwargs)


def test_process_ingestion_stores_encrypted_address_only_for_exact_areas(tmp_path, monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, class_=_PostgisAgnosticSession)
    monkeypatch.setattr(tasks_module, "SessionLocal", Session)
    monkeypatch.setenv("ADDRESS_ENCRYPTION_KEY", Fernet.generate_key().decode())
    db = Session()
    exact_area = SurveyArea(name="Exact area", authorization_ref="AUTH-6", precision="exact")
    coarse_area = SurveyArea(name="Coarse area", authorization_ref="AUTH-7", precision="coarse")
    db.add_all([exact_area, coarse_area]); db.flush()
    exact_run = SurveyRun(survey_area_id=exact_area.id, name="Exact run", authorization_ref="AUTH-6")
    coarse_run = SurveyRun(survey_area_id=coarse_area.id, name="Coarse run", authorization_ref="AUTH-7")
    db.add_all([exact_run, coarse_run]); db.flush()
    exact_raw = tmp_path / "exact.csv"
    exact_raw.write_text("MAC,FirstTime\n00:11:22:33:44:55,2026-09-08T12:00:00Z\n")
    coarse_raw = tmp_path / "coarse.csv"
    coarse_raw.write_text("MAC,FirstTime\nAA:BB:CC:DD:EE:FF,2026-09-08T12:00:00Z\n")
    exact_job = IngestionJob(survey_run_id=exact_run.id, filename="exact.csv", source_format="wigle", file_hash="3" * 64, raw_path=str(exact_raw))
    coarse_job = IngestionJob(survey_run_id=coarse_run.id, filename="coarse.csv", source_format="wigle", file_hash="4" * 64, raw_path=str(coarse_raw))
    db.add_all([exact_job, coarse_job]); db.commit()

    process_ingestion(exact_job.id)
    process_ingestion(coarse_job.id)

    exact_device = db.scalar(select(Device).join(Observation).where(Observation.survey_run_id == exact_run.id))
    coarse_device = db.scalar(select(Device).join(Observation).where(Observation.survey_run_id == coarse_run.id))
    assert exact_device.encrypted_address is not None
    assert decrypt_address(exact_device.encrypted_address) == "00:11:22:33:44:55"
    assert coarse_device.encrypted_address is None

    admin = Principal(1, "admin", "admin")
    revealed = reveal_device_address(exact_device.id, db=db, principal=admin)
    assert revealed["address"] == "00:11:22:33:44:55"
    with pytest.raises(HTTPException) as excinfo:
        reveal_device_address(coarse_device.id, db=db, principal=admin)
    assert excinfo.value.status_code == 409

    listed = devices(limit=100, offset=0, db=db, principal=admin)
    for item in listed["items"]:
        assert "encrypted_address" not in item
        assert "has_stored_address" in item


def test_process_ingestion_leaves_address_unset_without_an_encryption_key(tmp_path, monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, class_=_PostgisAgnosticSession)
    monkeypatch.setattr(tasks_module, "SessionLocal", Session)
    monkeypatch.delenv("ADDRESS_ENCRYPTION_KEY", raising=False)
    db = Session()
    area = SurveyArea(name="Exact but unconfigured", authorization_ref="AUTH-8", precision="exact")
    db.add(area); db.flush()
    run = SurveyRun(survey_area_id=area.id, name="Run", authorization_ref="AUTH-8")
    db.add(run); db.flush()
    raw = tmp_path / "capture.csv"
    raw.write_text("MAC,FirstTime\n00:11:22:33:44:55,2026-09-08T12:00:00Z\n")
    job = IngestionJob(survey_run_id=run.id, filename="capture.csv", source_format="wigle", file_hash="5" * 64, raw_path=str(raw))
    db.add(job); db.commit()

    process_ingestion(job.id)

    device = db.scalar(select(Device))
    assert device.encrypted_address is None


def test_list_areas_includes_counts_and_rename_updates_name():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    area = SurveyArea(name="Old name", authorization_ref="AUTH-9", precision="coarse")
    db.add(area); db.flush()
    run = SurveyRun(survey_area_id=area.id, name="Run", authorization_ref="AUTH-9")
    db.add(run); db.flush()
    device = Device(survey_area_id=area.id, token="g" * 64, oui_organization="unattributable", first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1))
    db.add(device); db.flush()
    db.add(Observation(survey_run_id=run.id, ingestion_job_id=1, device_id=device.id, captured_at=datetime(2026, 1, 1), protocol="wifi", quality=1, source_row=1))
    db.commit()
    admin = Principal(1, "admin", "admin")

    listed = list_areas(db=db, principal=admin)
    assert listed[0]["run_count"] == 1
    assert listed[0]["device_count"] == 1

    renamed = rename_area(area.id, AreaPatch(name="New name"), db=db, principal=admin)
    assert renamed["name"] == "New name"
    assert db.get(SurveyArea, area.id).name == "New name"

    with pytest.raises(HTTPException) as excinfo:
        rename_area(area.id, AreaPatch(name="   "), db=db, principal=admin)
    assert excinfo.value.status_code == 422


def test_device_vendor_summary_ranks_by_device_count_and_supports_area_filter():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    area_one = SurveyArea(name="Area one", authorization_ref="AUTH-10", precision="coarse")
    area_two = SurveyArea(name="Area two", authorization_ref="AUTH-11", precision="coarse")
    db.add_all([area_one, area_two]); db.flush()
    run_one = SurveyRun(survey_area_id=area_one.id, name="Run one", authorization_ref="AUTH-10")
    run_two = SurveyRun(survey_area_id=area_two.id, name="Run two", authorization_ref="AUTH-11")
    db.add_all([run_one, run_two]); db.flush()
    vendor_a_1 = Device(token="h" * 64, oui_organization="Vendor A", first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1))
    vendor_a_2 = Device(token="i" * 64, oui_organization="Vendor A", first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1))
    vendor_b = Device(token="j" * 64, oui_organization="Vendor B", first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1))
    db.add_all([vendor_a_1, vendor_a_2, vendor_b]); db.flush()
    db.add_all([
        Observation(survey_run_id=run_one.id, ingestion_job_id=1, device_id=vendor_a_1.id, captured_at=datetime(2026, 1, 1), protocol="wifi", quality=1, source_row=1),
        Observation(survey_run_id=run_one.id, ingestion_job_id=1, device_id=vendor_a_2.id, captured_at=datetime(2026, 1, 1), protocol="wifi", quality=1, source_row=2),
        Observation(survey_run_id=run_two.id, ingestion_job_id=1, device_id=vendor_b.id, captured_at=datetime(2026, 1, 1), protocol="wifi", quality=1, source_row=3),
    ])
    db.commit()
    viewer = Principal(1, "tester", "viewer")

    overall = device_vendor_summary(db=db, principal=viewer)
    assert overall[0] == {"oui_organization": "Vendor A", "device_count": 2, "share": round(2 / 3, 4)}
    assert overall[1] == {"oui_organization": "Vendor B", "device_count": 1, "share": round(1 / 3, 4)}

    scoped = device_vendor_summary(area_id=area_two.id, db=db, principal=viewer)
    assert scoped == [{"oui_organization": "Vendor B", "device_count": 1, "share": 1.0}]


def test_create_area_trims_whitespace_and_rejects_names_that_collide_after_trimming():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    analyst = Principal(1, "analyst", "analyst")

    created = create_area(AreaInput(name="Test 1", precision="exact"), db=db, principal=analyst)
    assert created["name"] == "Test 1"

    with pytest.raises(HTTPException) as excinfo:
        create_area(AreaInput(name="Test 1 ", precision="coarse"), db=db, principal=analyst)
    assert excinfo.value.status_code == 409
    assert db.scalar(select(func.count()).select_from(SurveyArea)) == 1


def test_purge_run_data_removes_orphaned_devices_even_when_filed_into_a_collection():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    area = SurveyArea(name="Filed area", authorization_ref="AUTH-12", precision="coarse")
    db.add(area); db.flush()
    run = SurveyRun(survey_area_id=area.id, name="Filed run", authorization_ref="AUTH-12")
    db.add(run); db.flush()
    # Matches real ingestion: Device.survey_area_id is never populated by
    # process_ingestion, so orphan detection must not depend on it matching
    # the run's area.
    device = Device(token="k" * 64, oui_organization="unattributable", first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1))
    db.add(device); db.flush()
    db.add(Observation(survey_run_id=run.id, ingestion_job_id=1, device_id=device.id, captured_at=datetime(2026, 1, 1), protocol="wifi", quality=1, source_row=1))
    db.commit()
    run_id, device_id = run.id, device.id
    admin = Principal(1, "admin", "admin")

    purge_run_data(db, run, admin)
    db.commit()
    assert db.scalar(select(SurveyRun).where(SurveyRun.id == run_id)) is None
    assert db.scalar(select(Device).where(Device.id == device_id)) is None


def test_survey_run_json_exposes_collection_id_not_the_survey_area_id_synonym():
    # SurveyRun.survey_area_id is a Python-only synonym for the real
    # collection_id column (see models.py); dump() walks __table__.columns,
    # so it only ever emits collection_id. The frontend must read that key,
    # not survey_area_id - a prior mismatch there silently broke the
    # Coverage/Baselines run-by-area filters and Surveys' filed/unfiled label.
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    area = SurveyArea(name="JSON shape area", authorization_ref="AUTH-13", precision="coarse")
    db.add(area); db.flush()
    run = SurveyRun(survey_area_id=area.id, name="Run", authorization_ref="AUTH-13")
    db.add(run); db.commit()
    admin = Principal(1, "admin", "admin")

    listed = list_runs(db=db, principal=admin)
    assert listed[0]["collection_id"] == area.id
    assert "survey_area_id" not in listed[0]
    assert dump(run) == listed[0]


def test_delete_area_rejects_a_collection_with_runs_but_allows_an_empty_one():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    admin = Principal(1, "admin", "admin")
    filed = SurveyArea(name="Has runs", authorization_ref="AUTH-14", precision="coarse")
    empty = SurveyArea(name="Empty", authorization_ref="AUTH-15", precision="exact")
    db.add_all([filed, empty]); db.flush()
    run = SurveyRun(survey_area_id=filed.id, name="Run", authorization_ref="AUTH-14")
    db.add(run); db.commit()

    with pytest.raises(HTTPException) as excinfo:
        delete_area(filed.id, db=db, principal=admin)
    assert excinfo.value.status_code == 409
    assert db.get(SurveyArea, filed.id) is not None

    result = delete_area(empty.id, db=db, principal=admin)
    assert result == {"status": "deleted", "area_id": empty.id}
    assert db.get(SurveyArea, empty.id) is None


def test_device_detail_derives_collections_via_observations_not_the_device_column():
    # Device.survey_area_id is never populated by real ingestion (see the
    # 2026-09-08 baseline/anomaly fix); device_detail's "collections" must be
    # derived from the device's own observations' runs instead, so this
    # deliberately leaves it unset to match reality.
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    area = SurveyArea(name="Filed area", authorization_ref="AUTH-16", precision="coarse")
    db.add(area); db.flush()
    run = SurveyRun(survey_area_id=area.id, name="Run", authorization_ref="AUTH-16")
    db.add(run); db.flush()
    device = Device(token="m" * 64, oui_organization="unattributable", first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1))
    db.add(device); db.flush()
    db.add(Observation(survey_run_id=run.id, ingestion_job_id=1, device_id=device.id, captured_at=datetime(2026, 1, 1), protocol="wifi", quality=1, source_row=1))
    db.commit()
    viewer = Principal(1, "tester", "viewer")

    detail = device_detail(device.id, limit=100, db=db, principal=viewer)
    assert detail["collections"] == ["Filed area"]
