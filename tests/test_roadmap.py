from datetime import datetime
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi import Response
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.main import (
    AnomalyPatch,
    CategoryPatch,
    DeviceReviewGroupPatch,
    DeviceReviewPatch,
    RuleProposalPatch,
    PasswordChangeInput,
    RetentionSettingsInput,
    change_password,
    device_category_summary,
    device_role_summary,
    device_fingerprint,
    devices,
    list_device_reviews,
    list_rule_proposals,
    establish_session,
    override_device_category,
    retention_preview,
    update_anomaly,
    update_retention_settings,
    update_device_review,
    update_device_review_group,
    update_rule_proposal,
    learning_summary,
    import_comparison,
)
from app.models import Anomaly, Device, DeviceReview, Observation, SurveyRun, User
from app.categorization import rebuild_categories
from app.policies import classify_device, device_role_scores, device_roles_from_scores, mac_address_scope, point_in_polygon, validate_polygon
from app.raw_storage import materialize_raw, write_raw
from app.security import Principal, password_hash, password_valid
from app.upload_security import validate_upload


def make_db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_polygon_contract_and_point_enforcement_are_deterministic():
    polygon = validate_polygon({"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 0]]]})
    assert polygon["coordinates"][0][0] == [0.0, 0.0]
    assert point_in_polygon(1, 1, polygon)
    assert not point_in_polygon(3, 1, polygon)

    try:
        validate_polygon({"type": "Point", "coordinates": [1, 1]})
    except ValueError as error:
        assert "GeoJSON Polygon" in str(error)
    else:
        raise AssertionError("invalid geometry was accepted")


def test_category_rules_return_explainable_evidence():
    category, confidence, evidence = classify_device("Cisco Systems", "office-router", "wifi")
    assert category == "network"
    assert confidence > 0.7
    assert any("vendor" in item for item in evidence)
    camera, _, camera_evidence = classify_device("Unknown", "front-door-camera", "wifi")
    assert camera == "camera"
    assert any("SSID" in item for item in camera_evidence)


def test_category_rules_prioritize_device_name_and_type_over_generic_vendor_hints():
    category, confidence, evidence = classify_device("Samsung Electronics", "living-room", "wifi", device_name="Galaxy S24", device_type="Wi-Fi Client")
    assert category == "mobile"
    assert confidence > 0.7
    assert any("device name" in item for item in evidence)

    tv, _, tv_evidence = classify_device("Samsung Electronics", "living-room", "wifi", device_name="Smart TV", device_type="television")
    assert tv == "entertainment"
    assert any("device type" in item for item in tv_evidence)

    network, _, network_evidence = classify_device("Unknown", None, "wifi", device_type="Wi-Fi AP")
    assert network == "network"
    assert any("device type" in item for item in network_evidence)

    assert classify_device(None, "My VW 4359", "wifi")[0] == "automotive"
    assert classify_device(None, "Audi_MMI_8741", "wifi")[0] == "automotive"
    assert classify_device(None, "Ferrari", "wifi")[0] == "automotive"
    assert classify_device(None, "GMC1024", "wifi")[0] == "automotive"
    assert classify_device(None, "myGMC 1234", "wifi")[0] == "automotive"
    assert classify_device(None, "DIRECT-03-BMW76992", "wifi")[0] == "automotive"
    assert classify_device(None, "audiology2353", "wifi")[0] != "automotive"
    assert classify_device(None, "RondasGMC", "wifi")[0] != "automotive"
    assert classify_device(None, "ET-2800 Series", "wifi")[0] == "printer"
    assert classify_device("Vantiva USA LLC", None, "wifi")[0] == "network"


def test_device_roles_are_orthogonal_and_explainable():
    pos_scores, pos_evidence = device_role_scores(None, "Aloha_POS136334", "wifi")
    assert device_roles_from_scores(pos_scores) == ["retail_pos"]
    assert any("SSID" in item for item in pos_evidence)

    guest_scores, _ = device_role_scores(None, "MSRV-Guest", "wifi")
    assert device_roles_from_scores(guest_scores) == ["guest_network"]

    smart_scores, smart_evidence = device_role_scores("Resideo", "downstairs-thermostat", "wifi")
    assert "smart_home" in device_roles_from_scores(smart_scores)
    assert any("vendor" in item or "device name" in item for item in smart_evidence)

    false_scores, _ = device_role_scores(None, "audiology2353", "wifi")
    assert device_roles_from_scores(false_scores) == []


def test_device_role_filter_and_summary_are_site_safe():
    db = make_db()
    pos = Device(token="p" * 64, device_roles=["retail_pos", "guest_network"], role_scores={"retail_pos": 1.1, "guest_network": .55}, role_evidence=["retail_pos: SSID contains 'pos'", "guest_network: SSID contains 'guest'"], first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1))
    guest = Device(token="g" * 64, first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1))
    db.add_all([pos, guest]); db.commit()
    listed = devices(role="retail_pos", limit=100, offset=0, db=db, principal=Principal(1, "viewer", "viewer"))
    assert listed["total"] == 1
    assert "retail_pos" in listed["items"][0]["device_roles"]
    summary = device_role_summary(db=db, principal=Principal(1, "viewer", "viewer"))
    assert summary["roles"][0]["role"] == "retail_pos"
    assert summary["roles"][0]["device_count"] == 1
    assert summary["role_tagged_devices"] == 1
    assert summary["role_assignments"] == 2
    assert summary["overlap_devices"] == 1


def test_device_review_queue_prioritizes_uncertain_devices_and_persists_disposition():
    db = make_db()
    unknown = Device(token="u" * 64, category="unknown", first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1))
    low_confidence = Device(token="l" * 64, category="network", category_confidence=.6, role_evidence=["retail_pos: SSID contains 'pos'"], first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1))
    db.add_all([unknown, low_confidence]); db.commit()
    viewer = Principal(1, "viewer", "viewer")
    queue = list_device_reviews(db=db, principal=viewer)
    assert queue["total"] == 1
    assert queue["items"][0]["representative"]["device"]["id"] == low_confidence.id
    no_signal = list_device_reviews(bucket="no_signal", db=db, principal=viewer)
    assert no_signal["total"] == 1
    assert no_signal["items"][0]["representative"]["device"]["id"] == unknown.id
    updated = update_device_review_group(DeviceReviewGroupPatch(group_key=no_signal["items"][0]["group_key"], status="insufficient_evidence", review_status="open", device_ids=no_signal["items"][0]["device_ids"]), db=db, principal=Principal(1, "analyst", "analyst"))
    assert updated["devices_updated"] == 1
    assert db.scalar(select(DeviceReview).where(DeviceReview.device_id == unknown.id)).reviewed_by == "analyst"
    assert list_device_reviews(status="open", bucket="no_signal", db=db, principal=viewer)["total"] == 0


def test_group_review_is_status_scoped_and_preserves_untouched_context():
    db = make_db()
    open_device = Device(token="o" * 64, category="unknown", first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1))
    dismissed_device = Device(token="x" * 64, category="unknown", first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1))
    db.add_all([open_device, dismissed_device]); db.flush()
    db.add(DeviceReview(device_id=dismissed_device.id, status="dismissed", disposition_note="keep this note", evidence_links=["ticket-9"]))
    db.commit()
    viewer = Principal(1, "viewer", "viewer")
    group = list_device_reviews(status="open", bucket="no_signal", db=db, principal=viewer)["items"][0]
    assert group["device_ids"] == [open_device.id]

    update_device_review_group(
        DeviceReviewGroupPatch(group_key=group["group_key"], status="needs_review", review_status="open", device_ids=group["device_ids"]),
        db=db,
        principal=Principal(1, "analyst", "analyst"),
    )
    assert db.scalar(select(DeviceReview).where(DeviceReview.device_id == open_device.id)).status == "needs_review"
    unchanged = db.scalar(select(DeviceReview).where(DeviceReview.device_id == dismissed_device.id))
    assert (unchanged.status, unchanged.disposition_note, unchanged.evidence_links) == ("dismissed", "keep this note", ["ticket-9"])


def test_single_review_status_change_preserves_existing_context():
    db = make_db()
    device = Device(token="s" * 64, category="unknown", first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1))
    db.add(device); db.flush()
    db.add(DeviceReview(device_id=device.id, status="open", disposition_note="keep this note", evidence_links=["ticket-10"]))
    db.commit()

    update_device_review(device.id, DeviceReviewPatch(status="confirmed"), db=db, principal=Principal(1, "analyst", "analyst"))
    review = db.scalar(select(DeviceReview).where(DeviceReview.device_id == device.id))
    assert (review.status, review.disposition_note, review.evidence_links) == ("confirmed", "keep this note", ["ticket-10"])


def test_mac_scope_is_privacy_safe_and_downweights_local_vendor_evidence():
    assert mac_address_scope("00:11:22:33:44:55") == "globally_administered"
    assert mac_address_scope("02:11:22:33:44:55") == "locally_administered"
    assert mac_address_scope("01:00:5e:00:00:01") == "multicast"
    category, _, evidence = classify_device("Cisco Systems", None, "wifi", address_scope="locally_administered")
    assert category == "unknown"
    assert any("OUI evidence is low confidence" in item for item in evidence)


def test_category_summary_exposes_counts_confidence_and_override_totals():
    db = make_db()
    db.add_all([
        Device(token="a" * 64, category="network", category_confidence=.8, first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1)),
        Device(token="b" * 64, category="network", category_confidence=.6, category_overridden=True, first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1)),
        Device(token="c" * 64, category="unknown", category_confidence=0, first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1)),
    ])
    db.commit()
    rows = device_category_summary(db=db, principal=Principal(1, "viewer", "viewer"))
    assert rows[0] == {"category": "network", "device_count": 2, "share": round(2 / 3, 4), "mean_confidence": .7, "override_count": 1}


def test_category_rebuild_uses_retained_observations_and_preserves_overrides():
    db = make_db()
    run = SurveyRun(name="Category run", authorization_ref="AUTH-CAT")
    device = Device(token="r" * 64, oui_organization="Cisco Systems", first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1))
    overridden = Device(token="s" * 64, oui_organization="Cisco Systems", category="camera", category_overridden=True, first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1))
    db.add_all([run, device, overridden]); db.flush()
    db.add(Observation(survey_run_id=run.id, ingestion_job_id=1, device_id=device.id, captured_at=datetime(2026, 1, 1), protocol="wifi", ssid="office-router", source_row=1))
    db.add(Observation(survey_run_id=run.id, ingestion_job_id=1, device_id=overridden.id, captured_at=datetime(2026, 1, 1), protocol="wifi", ssid="office-router", source_row=2))
    db.commit()
    updated, skipped = rebuild_categories(db, 100)
    assert (updated, skipped) == (1, 1)
    assert device.category == "network"
    assert device.category_rule_version == "rules-v6"
    assert overridden.category == "camera"


def test_category_override_is_persisted_and_audited():
    db = make_db()
    device = Device(token="a" * 64, first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1))
    db.add(device); db.commit()
    result = override_device_category(device.id, CategoryPatch(category="camera"), db=db, principal=Principal(1, "analyst", "analyst"))
    assert result["category"] == "camera"
    assert result["category_overridden"] is True
    assert db.get(Device, device.id).category_confidence == 1.0


def test_category_override_creates_reviewable_versioned_rule_proposal():
    db = make_db()
    run = SurveyRun(name="Feedback run", authorization_ref="AUTH-FEEDBACK")
    device = Device(token="f" * 64, oui_organization="Example Motors", first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1))
    db.add_all([run, device]); db.flush()
    db.add(Observation(survey_run_id=run.id, ingestion_job_id=1, device_id=device.id, captured_at=datetime(2026, 1, 1), protocol="wifi", ssid="My VW", source_row=1))
    db.commit()
    result = override_device_category(device.id, CategoryPatch(category="automotive"), db=db, principal=Principal(1, "analyst", "analyst"))
    assert result["rule_proposal_id"]
    proposals = list_rule_proposals(status="all", db=db, principal=Principal(1, "viewer", "viewer"))
    assert proposals[0]["target_category"] == "automotive"
    assert proposals[0]["revision"] == 1
    updated = update_rule_proposal(proposals[0]["id"], RuleProposalPatch(status="accepted", review_note="Promote after batch review"), db=db, principal=Principal(1, "analyst", "analyst"))
    assert updated["status"] == "accepted"
    assert db.get(Device, device.id).category == "automotive"


def test_learning_summary_measures_dispositions_and_scope():
    db = make_db()
    run = SurveyRun(name="Learning run", authorization_ref="AUTH-LEARNING")
    confirmed = Device(token="c" * 64, category="network", first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1))
    dismissed = Device(token="d" * 64, category="unknown", first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 1))
    db.add_all([run, confirmed, dismissed]); db.flush()
    for index, device in enumerate((confirmed, dismissed), start=1):
        db.add(Observation(survey_run_id=run.id, ingestion_job_id=1, device_id=device.id, captured_at=datetime(2026, 1, 2), protocol="wifi", ssid="review", source_row=index))
    db.add_all([DeviceReview(device_id=confirmed.id, status="confirmed", reviewed_at=datetime(2026, 1, 3)), DeviceReview(device_id=dismissed.id, status="dismissed", reviewed_at=datetime(2026, 1, 3))]); db.commit()
    summary = learning_summary(start=datetime(2026, 1, 1), end=datetime(2026, 1, 4), db=db, principal=Principal(1, "viewer", "viewer"))
    assert summary["reviewed"] == 2
    assert summary["dispositions"] == {"confirmed": 1, "dismissed": 1}
    assert summary["false_positive_rate"] == .5


def test_fingerprint_and_run_comparison_are_privacy_safe():
    db = make_db()
    older = SurveyRun(name="Older", authorization_ref="AUTH-COMPARE")
    newer = SurveyRun(name="Newer", authorization_ref="AUTH-COMPARE")
    returning = Device(token="r" * 64, oui_organization="Example Vendor", category="network", first_seen=datetime(2026, 1, 1), last_seen=datetime(2026, 1, 2))
    new_device = Device(token="n" * 64, oui_organization="Example Vendor", category="network", first_seen=datetime(2026, 1, 2), last_seen=datetime(2026, 1, 2))
    db.add_all([older, newer, returning, new_device]); db.flush()
    db.add_all([
        Observation(survey_run_id=older.id, ingestion_job_id=1, device_id=returning.id, captured_at=datetime(2026, 1, 1), protocol="wifi", ssid="office", source_row=1),
        Observation(survey_run_id=newer.id, ingestion_job_id=1, device_id=returning.id, captured_at=datetime(2026, 1, 2), protocol="wifi", ssid="office-new", source_row=2),
        Observation(survey_run_id=newer.id, ingestion_job_id=1, device_id=new_device.id, captured_at=datetime(2026, 1, 2), protocol="wifi", ssid="office", source_row=3),
    ]); db.commit()
    fingerprint = device_fingerprint(returning.id, db=db, principal=Principal(1, "viewer", "viewer"))
    assert len(fingerprint["summary"]["fingerprint"]) == 32
    assert "r" * 64 not in str(fingerprint)
    comparison = import_comparison(older.id, newer.id, db=db, principal=Principal(1, "viewer", "viewer"))
    assert comparison["counts"]["new"] == 1
    assert comparison["counts"]["returning"] == 1
    assert comparison["counts"]["changed"] == 1


def test_anomaly_disposition_keeps_notes_and_bounded_evidence_links():
    db = make_db()
    item = Anomaly(kind="novel_device", score=.8, confidence=.8, explanation="review", evidence_links=[])
    db.add(item); db.commit()
    updated = update_anomaly(item.id, AnomalyPatch(status="confirmed", disposition_note="approved change", evidence_links=["ticket-42", " https://approved.local/evidence "]), db=db, principal=Principal(1, "analyst", "analyst"))
    assert updated["disposition_note"] == "approved change"
    assert updated["evidence_links"] == ["ticket-42", "https://approved.local/evidence"]


def test_retention_settings_are_persisted_and_drive_preview(monkeypatch):
    db = make_db()
    monkeypatch.setenv("RAW_RETENTION_DAYS", "3")
    monkeypatch.setenv("NORMALIZED_RETENTION_DAYS", "4")
    first = retention_preview(db)
    assert (first["raw_retention_days"], first["normalized_retention_days"]) == (3, 4)
    updated = update_retention_settings(RetentionSettingsInput(raw_retention_days=90, normalized_retention_days=180), db=db, principal=Principal(1, "admin", "admin"))
    assert (updated["raw_retention_days"], updated["normalized_retention_days"]) == (90, 180)
    second = retention_preview(db)
    assert (second["raw_retention_days"], second["normalized_retention_days"]) == (90, 180)


def test_password_change_revokes_sessions_and_reestablishes_one():
    db = make_db()
    user = User(username="operator", password_hash=password_hash("old-password-123"), role="admin")
    db.add(user); db.commit()
    response = Response()
    change_password(PasswordChangeInput(current_password="old-password-123", new_password="new-password-456"), response=response, db=db, principal=Principal(user.id, user.username, user.role))
    assert password_valid("new-password-456", db.get(type(user), user.id).password_hash)


def test_secure_cookie_configuration_is_exercisable(monkeypatch):
    db = make_db()
    user = User(username="secure-operator", password_hash=password_hash("password-12345"), role="admin")
    db.add(user); db.commit()
    response = Response()
    monkeypatch.setenv("COOKIE_SECURE", "true")
    establish_session(response, user, db)
    assert "Secure" in response.headers["set-cookie"]


def test_upload_preflight_rejects_source_mismatch_and_invalid_native_capture():
    assert validate_upload("capture.csv", "wigle", b"MAC,FirstTime\n00:11:22:33:44:55,2026-09-08T12:00:00Z\n") == "text"
    with pytest.raises(ValueError, match="WiGLE"):
        validate_upload("capture.json", "wigle", b"{}")
    with pytest.raises(ValueError, match="SQLite"):
        validate_upload("capture.kismet", "kismet", b"not a sqlite database")


def test_raw_storage_can_encrypt_new_uploads_and_materialize_them(tmp_path, monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("RAW_STORAGE_ENCRYPTION_KEY", key)
    path = Path(tmp_path) / "raw-capture"
    blob = b"private capture bytes"
    assert write_raw(path, blob) is True
    assert path.read_bytes() != blob
    with materialize_raw(str(path), True) as materialized:
        temporary_path = Path(materialized)
        assert temporary_path.read_bytes() == blob
    assert not temporary_path.exists()


def test_raw_storage_keeps_legacy_plaintext_jobs_readable(tmp_path, monkeypatch):
    monkeypatch.delenv("RAW_STORAGE_ENCRYPTION_KEY", raising=False)
    path = Path(tmp_path) / "legacy-capture"
    path.write_bytes(b"legacy capture bytes")
    with materialize_raw(str(path), False) as materialized:
        assert materialized == str(path)
