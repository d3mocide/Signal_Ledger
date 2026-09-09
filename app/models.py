from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, synonym
from .database import Base

class Collection(Base):
    __tablename__ = "collections"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    authorization_ref: Mapped[str] = mapped_column(String(240))
    purpose: Mapped[str] = mapped_column(Text, default="asset awareness")
    precision: Mapped[str] = mapped_column(String(24), default="coarse")
    polygon: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class CaptureSession(Base):
    __tablename__ = "capture_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    collection_id: Mapped[int | None] = mapped_column(ForeignKey("collections.id"), index=True, nullable=True)
    survey_area_id = synonym("collection_id")  # temporary Python compatibility; no legacy DB column
    name: Mapped[str] = mapped_column(String(160))
    authorization_ref: Mapped[str] = mapped_column(String(240))
    collector_coverage: Mapped[float] = mapped_column(Float, default=1.0)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    capture_session_id: Mapped[int] = mapped_column(ForeignKey("capture_sessions.id"), index=True)
    survey_run_id = synonym("capture_session_id")
    filename: Mapped[str] = mapped_column(String(255))
    source_format: Mapped[str] = mapped_column(String(32))
    file_hash: Mapped[str] = mapped_column(String(64), unique=True)
    raw_path: Mapped[str] = mapped_column(String(400))
    raw_encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    parser_version: Mapped[str] = mapped_column(String(32), default="v1")
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    collection_id: Mapped[int | None] = mapped_column(ForeignKey("collections.id"), index=True, nullable=True)
    survey_area_id = synonym("collection_id")
    token: Mapped[str] = mapped_column(String(64), index=True)
    oui_prefix: Mapped[str | None] = mapped_column(String(8), nullable=True)
    oui_organization: Mapped[str] = mapped_column(String(160), default="unattributable")
    category: Mapped[str] = mapped_column(String(48), default="unknown")
    category_confidence: Mapped[float] = mapped_column(Float, default=0)
    category_evidence: Mapped[list] = mapped_column(JSON, default=list)
    category_scores: Mapped[dict] = mapped_column(JSON, default=dict)
    category_rule_version: Mapped[str] = mapped_column(String(32), default="rules-v6")
    category_overridden: Mapped[bool] = mapped_column(Boolean, default=False)
    device_roles: Mapped[list] = mapped_column(JSON, default=list)
    role_scores: Mapped[dict] = mapped_column(JSON, default=dict)
    role_evidence: Mapped[list] = mapped_column(JSON, default=list)
    role_rule_version: Mapped[str] = mapped_column(String(32), default="roles-v1")
    address_scope: Mapped[str] = mapped_column(String(32), default="unknown")
    first_seen: Mapped[datetime] = mapped_column(DateTime)
    last_seen: Mapped[datetime] = mapped_column(DateTime)
    encrypted_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    __table_args__ = (UniqueConstraint("token", name="uq_device_token"),)

class DeviceReview(Base):
    __tablename__ = "device_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    disposition_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_links: Mapped[list] = mapped_column(JSON, default=list)
    reviewed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class OUIImport(Base):
    __tablename__ = "oui_imports"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_name: Mapped[str] = mapped_column(String(255))
    source_hash: Mapped[str] = mapped_column(String(64), unique=True)
    registry_version: Mapped[str] = mapped_column(String(80))
    assignments: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class OUIAssignment(Base):
    __tablename__ = "oui_assignments"
    prefix: Mapped[str] = mapped_column(String(6), primary_key=True)
    organization: Mapped[str] = mapped_column(String(255))
    import_id: Mapped[int] = mapped_column(ForeignKey("oui_imports.id"), index=True)

class Observation(Base):
    __tablename__ = "observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    capture_session_id: Mapped[int] = mapped_column(ForeignKey("capture_sessions.id"), index=True)
    survey_run_id = synonym("capture_session_id")
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    ingestion_job_id: Mapped[int] = mapped_column(ForeignKey("ingestion_jobs.id"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    protocol: Mapped[str] = mapped_column(String(16), index=True)
    ssid: Mapped[str | None] = mapped_column(String(160), nullable=True)
    device_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    device_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    security: Mapped[str | None] = mapped_column(String(80), nullable=True)
    rssi: Mapped[float | None] = mapped_column(Float, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    spatial_cell: Mapped[str | None] = mapped_column(String(32), nullable=True)
    quality: Mapped[float] = mapped_column(Float, default=1.0)
    source_row: Mapped[int] = mapped_column(Integer)

class Baseline(Base):
    __tablename__ = "baselines"
    id: Mapped[int] = mapped_column(primary_key=True)
    collection_id: Mapped[int | None] = mapped_column(ForeignKey("collections.id"), index=True, nullable=True)
    survey_area_id = synonym("collection_id")
    name: Mapped[str] = mapped_column(String(160))
    run_ids: Mapped[list] = mapped_column(JSON)
    expectations: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Anomaly(Base):
    __tablename__ = "anomalies"
    id: Mapped[int] = mapped_column(primary_key=True)
    collection_id: Mapped[int | None] = mapped_column(ForeignKey("collections.id"), index=True, nullable=True)
    survey_area_id = synonym("collection_id")
    baseline_id: Mapped[int | None] = mapped_column(ForeignKey("baselines.id"), nullable=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(48))
    score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    explanation: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="open")
    disposition_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_links: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class SavedFilter(Base):
    __tablename__ = "saved_filters"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    owner: Mapped[str] = mapped_column(String(120))
    resource: Mapped[str] = mapped_column(String(32), default="observations")
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(120), index=True)
    role: Mapped[str] = mapped_column(String(24))
    action: Mapped[str] = mapped_column(String(96), index=True)
    resource_type: Mapped[str] = mapped_column(String(48))
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(24), default="viewer")
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class LoginSession(Base):
    __tablename__ = "login_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class WorkspaceSetting(Base):
    __tablename__ = "workspace_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    raw_retention_days: Mapped[int] = mapped_column(Integer, default=30)
    normalized_retention_days: Mapped[int] = mapped_column(Integer, default=365)
    updated_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

# Public domain names. Compatibility aliases will be removed after endpoint cleanup.
SurveyArea = Collection
SurveyRun = CaptureSession
