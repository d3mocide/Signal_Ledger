from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

class SurveyArea(Base):
    __tablename__ = "survey_areas"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    authorization_ref: Mapped[str] = mapped_column(String(240))
    purpose: Mapped[str] = mapped_column(Text, default="asset awareness")
    precision: Mapped[str] = mapped_column(String(24), default="coarse")
    polygon: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class SurveyRun(Base):
    __tablename__ = "survey_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    survey_area_id: Mapped[int] = mapped_column(ForeignKey("survey_areas.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    authorization_ref: Mapped[str] = mapped_column(String(240))
    collector_coverage: Mapped[float] = mapped_column(Float, default=1.0)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    survey_run_id: Mapped[int] = mapped_column(ForeignKey("survey_runs.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    source_format: Mapped[str] = mapped_column(String(32))
    file_hash: Mapped[str] = mapped_column(String(64), unique=True)
    raw_path: Mapped[str] = mapped_column(String(400))
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    parser_version: Mapped[str] = mapped_column(String(32), default="v1")
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    survey_area_id: Mapped[int] = mapped_column(ForeignKey("survey_areas.id"), index=True)
    token: Mapped[str] = mapped_column(String(64), index=True)
    oui_prefix: Mapped[str | None] = mapped_column(String(8), nullable=True)
    oui_organization: Mapped[str] = mapped_column(String(160), default="unattributable")
    category: Mapped[str] = mapped_column(String(48), default="unknown")
    category_confidence: Mapped[float] = mapped_column(Float, default=0)
    first_seen: Mapped[datetime] = mapped_column(DateTime)
    last_seen: Mapped[datetime] = mapped_column(DateTime)
    __table_args__ = (UniqueConstraint("survey_area_id", "token", name="uq_area_device_token"),)

class Observation(Base):
    __tablename__ = "observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    survey_run_id: Mapped[int] = mapped_column(ForeignKey("survey_runs.id"), index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    ingestion_job_id: Mapped[int] = mapped_column(ForeignKey("ingestion_jobs.id"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    protocol: Mapped[str] = mapped_column(String(16), index=True)
    ssid: Mapped[str | None] = mapped_column(String(160), nullable=True)
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
    survey_area_id: Mapped[int] = mapped_column(ForeignKey("survey_areas.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    run_ids: Mapped[list] = mapped_column(JSON)
    expectations: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Anomaly(Base):
    __tablename__ = "anomalies"
    id: Mapped[int] = mapped_column(primary_key=True)
    survey_area_id: Mapped[int] = mapped_column(ForeignKey("survey_areas.id"), index=True)
    baseline_id: Mapped[int | None] = mapped_column(ForeignKey("baselines.id"), nullable=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(48))
    score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    explanation: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="open")
    disposition_note: Mapped[str | None] = mapped_column(Text, nullable=True)
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
