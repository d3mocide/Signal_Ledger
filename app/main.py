import csv, hashlib, io, os, time
import urllib.error, urllib.request
from collections import Counter, defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from redis import Redis
from rq import Queue
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .crypto import decrypt_address
from .database import SessionLocal
from .migrations import upgrade
from .models import Anomaly, AuditEvent, Baseline, Device, IngestionJob, LoginSession, Observation, OUIAssignment, OUIImport, SavedFilter, SurveyArea, SurveyRun, User
from .security import Principal, ROLE_ORDER, ROLES, SESSION_COOKIE, authenticate, expires_at, password_hash, password_valid, session_token, token_hash
from .tasks import process_ingestion

CARTO_API_KEY = os.getenv("CARTO_API_KEY") or None
IEEE_OUI_URL = "https://standards-oui.ieee.org/oui/oui.csv"
RAW = Path(os.getenv("RAW_STORAGE_PATH", "/tmp/signal-ledger/raw")); RAW.mkdir(parents=True, exist_ok=True)
redis = Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0")); queue = Queue("signal-ledger", connection=redis)
MAX_UPLOAD = 100 * 1024 * 1024; ALLOWED_SUFFIXES = {".csv", ".json", ".ndjson", ".kismet"}
MAX_OUI_UPLOAD = 20 * 1024 * 1024
@asynccontextmanager
async def lifespan(app):
    for _ in range(20):
        try: upgrade(); break
        except Exception: time.sleep(1)
    yield
app = FastAPI(title="Signal Ledger", version="0.2.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/assets", StaticFiles(directory="app/static/assets"), name="assets")
@app.middleware("http")
async def request_database(request, call_next):
    if not request.url.path.startswith(("/assets", "/static", "/health")):
        try:
            key = f"rate:{request.client.host if request.client else 'unknown'}:{request.url.path}"
            current = redis.incr(key)
            if current == 1: redis.expire(key, 60)
            if current > int(os.getenv("RATE_LIMIT_PER_MINUTE", "120")):
                return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
        except Exception: pass
    request.state.db = SessionLocal()
    try:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        return response
    finally: request.state.db.close()
def db_session():
    db = SessionLocal()
    try: yield db
    finally: db.close()
def dump(obj): return {column.name: getattr(obj, column.name) for column in obj.__table__.columns}
def job_view(job):
    data = dump(job)
    data.pop("raw_path", None)
    data.pop("file_hash", None)
    return data
def device_view(device):
    data = dump(device)
    data["has_stored_address"] = data.pop("encrypted_address") is not None
    return data
def filtered_observations(query, area_id=None, run_id=None, device_id=None, protocol=None, vendor=None, category=None, start=None, end=None, min_quality=None, min_rssi=None):
    """Apply the same bounded discovery filters to queries already joined to runs/devices."""
    if area_id: query = query.where(SurveyRun.survey_area_id == area_id)
    if run_id: query = query.where(Observation.survey_run_id == run_id)
    if device_id: query = query.where(Observation.device_id == device_id)
    if protocol: query = query.where(Observation.protocol == protocol)
    if vendor: query = query.where(Device.oui_organization.ilike(f"%{vendor}%"))
    if category: query = query.where(Device.category == category)
    if start: query = query.where(Observation.captured_at >= start)
    if end: query = query.where(Observation.captured_at <= end)
    if min_quality is not None: query = query.where(Observation.quality >= min_quality)
    if min_rssi is not None: query = query.where(Observation.rssi >= min_rssi)
    return query
def ensure(principal, minimum):
    if ROLE_ORDER[principal.role] < ROLE_ORDER[minimum]: raise HTTPException(403, f"{minimum} role required")
def audit(db, principal, action, resource_type, resource_id=None, detail=None):
    db.add(AuditEvent(actor=principal.actor, role=principal.role, action=action, resource_type=resource_type, resource_id=str(resource_id) if resource_id else None, detail=detail or {}))
def purge_run_data(db, run, principal, action="survey_run.deleted"):
    """Remove a run transactionally; unlink returned source files after commit."""
    run_id, area_id = run.id, run.survey_area_id
    job_ids = list(db.scalars(select(IngestionJob.id).where(IngestionJob.survey_run_id == run_id)).all())
    raw_paths = list(db.scalars(select(IngestionJob.raw_path).where(IngestionJob.survey_run_id == run_id)).all())
    for baseline in list(db.scalars(select(Baseline).where(Baseline.survey_area_id == area_id)).all()):
        if run_id in baseline.run_ids:
            db.execute(delete(Anomaly).where(Anomaly.baseline_id == baseline.id)); db.delete(baseline)
    # Devices are never scoped to an area (Device.survey_area_id is not
    # populated by ingestion), so orphan detection is scoped to this run's own
    # devices instead - not a survey_area_id match, which would never hit.
    device_ids = list(db.scalars(select(Observation.device_id).where(Observation.survey_run_id == run_id).distinct()).all())
    db.execute(delete(Observation).where(Observation.survey_run_id == run_id))
    db.execute(delete(IngestionJob).where(IngestionJob.survey_run_id == run_id))
    db.delete(run)
    orphan_ids = list(db.scalars(select(Device.id).where(Device.id.in_(device_ids), ~select(Observation.id).where(Observation.device_id == Device.id).exists())).all()) if device_ids else []
    if orphan_ids:
        db.execute(delete(Anomaly).where(Anomaly.device_id.in_(orphan_ids)))
        db.execute(delete(Device).where(Device.id.in_(orphan_ids)))
    audit(db, principal, action, "survey_run", run_id, {"ingestion_jobs": job_ids, "orphaned_devices_removed": len(orphan_ids)})
    return raw_paths
def protected(minimum):
    def dependency(principal: Principal = Depends(authenticate)):
        ensure(principal, minimum); return principal
    return dependency
class AreaInput(BaseModel):
    name: str = Field(max_length=160); authorization_ref: str = Field(default="", max_length=240); purpose: str = Field(default="personal collection", max_length=2000); precision: str = "coarse"; polygon: dict | None = None
class AreaPatch(BaseModel):
    name: str = Field(max_length=160)
class RunInput(BaseModel):
    survey_area_id: int; name: str = Field(max_length=160); authorization_ref: str = Field(default="", max_length=240); collector_coverage: float = Field(1, ge=0, le=1)
class FilterInput(BaseModel):
    name: str = Field(max_length=120); resource: str = "observations"; filters: dict
class Credentials(BaseModel):
    username: str = Field(pattern=r"^[a-zA-Z0-9_.-]{3,80}$"); password: str = Field(min_length=10, max_length=256)
class UserInput(Credentials):
    role: str
class UserPatch(BaseModel):
    disabled: bool
class BaselineInput(BaseModel):
    survey_area_id: int
    name: str = Field(min_length=3, max_length=160)
    run_ids: list[int] = Field(min_length=1, max_length=100)
class AnomalyPatch(BaseModel):
    status: str
    disposition_note: str | None = Field(default=None, max_length=2000)
class RetentionSweepInput(BaseModel):
    confirm: str = Field(max_length=32)
class CollectionAssignment(BaseModel):
    name: str = Field(min_length=1, max_length=160)

def baseline_expectations(db, area_id, run_ids):
    # run_ids are already validated (in create_baseline) to belong to area_id,
    # so no area filter is needed here; Device.survey_area_id is never
    # populated by real ingestion and must not be used to scope this query.
    rows = db.execute(select(Observation, Device).join(Device).where(Observation.survey_run_id.in_(run_ids))).all()
    devices, vendors, categories = set(), set(), set()
    cells, hours, profiles = defaultdict(set), defaultdict(set), defaultdict(set)
    for observation, device in rows:
        devices.add(device.token)
        if device.oui_organization != "unattributable": vendors.add(device.oui_organization)
        categories.add(device.category)
        if observation.spatial_cell: cells[device.token].add(observation.spatial_cell)
        hours[device.token].add(observation.captured_at.hour)
        if observation.protocol == "wifi": profiles[device.token].add(f"{observation.ssid or ''}|{observation.security or ''}")
    coverage = db.scalars(select(SurveyRun.collector_coverage).where(SurveyRun.id.in_(run_ids))).all()
    return {"version": "rules-v1", "devices": sorted(devices), "vendors": sorted(vendors), "categories": sorted(categories), "cells": {key: sorted(value) for key, value in cells.items()}, "hours": {key: sorted(value) for key, value in hours.items()}, "profiles": {key: sorted(value) for key, value in profiles.items()}, "coverage_mean": round(sum(coverage) / len(coverage), 3) if coverage else 0}

def build_anomalies(db, baseline):
    expectation = baseline.expectations or {}; known = set(expectation.get("devices", [])); vendors = set(expectation.get("vendors", [])); cells = expectation.get("cells", {}); hours = expectation.get("hours", {}); profiles = expectation.get("profiles", {})
    db.execute(delete(Anomaly).where(Anomaly.baseline_id == baseline.id))
    observations = db.execute(select(Observation, Device).join(Device).join(SurveyRun).where(SurveyRun.survey_area_id == baseline.survey_area_id, ~Observation.survey_run_id.in_(baseline.run_ids))).all()
    emitted = set()
    def emit(kind, device, score, confidence, explanation):
        key = (kind, device.id if device else None)
        if key in emitted: return
        emitted.add(key); db.add(Anomaly(survey_area_id=baseline.survey_area_id, baseline_id=baseline.id, device_id=device.id if device else None, kind=kind, score=score, confidence=confidence, explanation=explanation))
    for observation, device in observations:
        if device.token not in known:
            emit("novel_device", device, .8, .8, "Device token was not present in the frozen baseline training runs.")
            if device.oui_organization != "unattributable" and device.oui_organization not in vendors: emit("novel_vendor", device, .7, .75, "Valid OUI organization was not present in the frozen baseline.")
            continue
        if observation.spatial_cell and cells.get(device.token) and observation.spatial_cell not in cells[device.token]: emit("spatial_outlier", device, .65, .65, "Known device appeared in a coarse cell outside its baseline footprint.")
        if hours.get(device.token) and observation.captured_at.hour not in hours[device.token]: emit("temporal_outlier", device, .55, .55, "Known device appeared outside its baseline hour-of-day window.")
        profile = f"{observation.ssid or ''}|{observation.security or ''}"
        if observation.protocol == "wifi" and profiles.get(device.token) and profile not in profiles[device.token]: emit("profile_change", device, .7, .65, "Known Wi-Fi device has a new SSID/security profile relative to its baseline.")
    for run in db.scalars(select(SurveyRun).where(SurveyRun.survey_area_id == baseline.survey_area_id, ~SurveyRun.id.in_(baseline.run_ids))).all():
        if expectation.get("coverage_mean", 0) and run.collector_coverage < expectation["coverage_mean"] * .7: emit("coverage_anomaly", None, .4, .8, f"Run '{run.name}' reports coverage below 70% of the baseline mean; treat other findings cautiously.")
    db.flush()

def establish_session(response, user, db):
    token = session_token()
    db.add(LoginSession(user_id=user.id, token_hash=token_hash(token), expires_at=expires_at()))
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="strict", secure=os.getenv("COOKIE_SECURE", "false").lower() == "true", max_age=int(os.getenv("SESSION_DAYS", "7")) * 86400)

@app.get("/")
def home(): return FileResponse("app/static/index.html")
@app.get("/health")
def health(): return {"status": "ok", "queue": "signal-ledger", "version": app.version}
@app.get("/v1/setup/status")
def setup_status(db: Session = Depends(db_session)):
    return {"setup_required": db.scalar(select(func.count()).select_from(User)) == 0}
@app.post("/v1/setup")
def setup_owner(body: Credentials, response: Response, db: Session = Depends(db_session)):
    if db.scalar(select(func.count()).select_from(User)) != 0: raise HTTPException(409, "Initial setup is already complete")
    user = User(username=body.username, password_hash=password_hash(body.password), role="admin")
    db.add(user); db.flush()
    audit(db, Principal(user.id, user.username, user.role), "user.initialized", "user", user.id)
    establish_session(response, user, db); db.commit()
    return {"username": user.username, "role": user.role}
@app.post("/v1/auth/login")
def login(body: Credentials, response: Response, db: Session = Depends(db_session)):
    user = db.scalar(select(User).where(User.username == body.username))
    if not user or not password_valid(body.password, user.password_hash): raise HTTPException(401, "Invalid username or password")
    if user.disabled: raise HTTPException(403, "User account is disabled")
    establish_session(response, user, db); audit(db, Principal(user.id, user.username, user.role), "auth.login", "user", user.id); db.commit()
    return {"username": user.username, "role": user.role}
@app.post("/v1/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(db_session), principal: Principal = Depends(authenticate)):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        session = db.scalar(select(LoginSession).where(LoginSession.token_hash == token_hash(token)))
        if session: db.delete(session)
    audit(db, principal, "auth.logout", "user", principal.user_id); db.commit(); response.delete_cookie(SESSION_COOKIE)
    return {"status": "signed_out"}
@app.get("/v1/me")
def me(principal: Principal = Depends(authenticate)): return {"actor": principal.actor, "role": principal.role, "map_tile_key": CARTO_API_KEY}
@app.post("/v1/users")
def create_user(body: UserInput, db: Session = Depends(db_session), principal: Principal = Depends(protected("admin"))):
    if body.role not in ROLES: raise HTTPException(422, "Unknown role")
    if db.scalar(select(User).where(User.username == body.username)): raise HTTPException(409, "Username already exists")
    user = User(username=body.username, password_hash=password_hash(body.password), role=body.role)
    db.add(user); db.flush(); audit(db, principal, "user.created", "user", user.id, {"role": user.role}); db.commit()
    return {"id": user.id, "username": user.username, "role": user.role, "disabled": user.disabled}
@app.get("/v1/users")
def list_users(db: Session = Depends(db_session), principal: Principal = Depends(protected("admin"))):
    return [{"id": item.id, "username": item.username, "role": item.role, "disabled": item.disabled, "created_at": item.created_at} for item in db.scalars(select(User).order_by(User.username)).all()]
@app.patch("/v1/users/{user_id}")
def update_user(user_id: int, body: UserPatch, db: Session = Depends(db_session), principal: Principal = Depends(protected("admin"))):
    user = db.get(User, user_id)
    if not user: raise HTTPException(404, "User not found")
    if user.id == principal.user_id and body.disabled: raise HTTPException(422, "You cannot disable your own active administrator account")
    user.disabled = body.disabled
    if body.disabled: db.execute(delete(LoginSession).where(LoginSession.user_id == user.id))
    audit(db, principal, "user.disabled" if body.disabled else "user.enabled", "user", user.id); db.commit()
    return {"id": user.id, "username": user.username, "disabled": user.disabled}
@app.delete("/v1/users/{user_id}/sessions")
def revoke_user_sessions(user_id: int, db: Session = Depends(db_session), principal: Principal = Depends(protected("admin"))):
    if not db.get(User, user_id): raise HTTPException(404, "User not found")
    removed = db.execute(delete(LoginSession).where(LoginSession.user_id == user_id)).rowcount
    audit(db, principal, "user.sessions_revoked", "user", user_id, {"sessions": removed}); db.commit()
    return {"revoked": removed}
@app.get("/v1/oui/status")
def oui_status(db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))):
    latest = db.scalar(select(OUIImport).order_by(OUIImport.created_at.desc()))
    return {"assignments": db.scalar(select(func.count()).select_from(OUIAssignment)), "latest": dump(latest) if latest else None}
def apply_oui_csv(db: Session, principal: Principal, blob: bytes, source_name: str, registry_version: str, action: str):
    if not blob or len(blob) > MAX_OUI_UPLOAD: raise HTTPException(413, "OUI registry must be 1 byte to 20 MB")
    digest = hashlib.sha256(blob).hexdigest()
    existing = db.scalar(select(OUIImport).where(OUIImport.source_hash == digest))
    if existing: return {"idempotent": True, **dump(existing)}
    try: rows = list(csv.DictReader(io.StringIO(blob.decode("utf-8-sig", errors="replace"))))
    except csv.Error: raise HTTPException(422, "Invalid OUI CSV")
    assignments = {}
    for row in rows:
        prefix = (row.get("Assignment") or "").strip().upper().replace("-", "")
        organization = (row.get("Organization Name") or "").strip()
        if len(prefix) == 6 and all(char in "0123456789ABCDEF" for char in prefix) and organization: assignments[prefix] = organization[:255]
    if len(assignments) < 100: raise HTTPException(422, "CSV does not look like an IEEE MA-L registry")
    item = OUIImport(source_name=source_name[:255], source_hash=digest, registry_version=registry_version[:80], assignments=len(assignments)); db.add(item); db.flush()
    db.execute(delete(OUIAssignment)); db.add_all([OUIAssignment(prefix=prefix, organization=organization, import_id=item.id) for prefix, organization in assignments.items()])
    catalog = assignments
    for device in db.scalars(select(Device).where(Device.oui_prefix.is_not(None))).all(): device.oui_organization = catalog.get(device.oui_prefix, "unattributable")
    audit(db, principal, action, "oui_import", item.id, {"assignments": len(assignments), "registry_version": item.registry_version}); db.commit()
    return dump(item)
@app.post("/v1/oui/import")
async def import_oui(file: UploadFile = File(...), registry_version: str = "IEEE MA-L", db: Session = Depends(db_session), principal: Principal = Depends(protected("admin"))):
    if Path(file.filename or "").suffix.lower() != ".csv": raise HTTPException(415, "Upload the IEEE CSV registry")
    blob = await file.read()
    return apply_oui_csv(db, principal, blob, Path(file.filename or "oui.csv").name, registry_version, "oui.imported")
@app.post("/v1/oui/refresh")
def refresh_oui(db: Session = Depends(db_session), principal: Principal = Depends(protected("admin"))):
    request = urllib.request.Request(IEEE_OUI_URL, headers={"User-Agent": "signal-ledger-oui-refresh/1"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            blob = response.read(MAX_OUI_UPLOAD + 1)
    except (urllib.error.URLError, TimeoutError) as error:
        raise HTTPException(502, "Could not reach the IEEE OUI registry: " + str(getattr(error, "reason", error)))
    return apply_oui_csv(db, principal, blob, "oui.csv (fetched from IEEE)", "IEEE MA-L", "oui.refreshed")
@app.get("/v1/overview")
def overview(db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))):
    count = lambda table: db.scalar(select(func.count()).select_from(table))
    return {"areas": count(SurveyArea), "runs": count(SurveyRun), "observations": count(Observation), "devices": count(Device), "unattributable": db.scalar(select(func.count()).select_from(Device).where(Device.oui_organization == "unattributable")), "completed_runs": db.scalar(select(func.count()).select_from(SurveyRun).where(SurveyRun.completed == True))}
@app.post("/v1/survey-areas")
def create_area(body: AreaInput, db: Session = Depends(db_session), principal: Principal = Depends(protected("analyst"))):
    if body.precision not in {"coarse", "exact"}: raise HTTPException(422, "precision must be coarse or exact")
    name = body.name.strip()
    if not name: raise HTTPException(422, "name must not be empty")
    if db.scalar(select(SurveyArea).where(SurveyArea.name == name)): raise HTTPException(409, "A collection with that name already exists")
    data = body.model_dump(); data["name"] = name; data["authorization_ref"] = data["authorization_ref"].strip()
    area = SurveyArea(**data); db.add(area)
    try:
        db.flush(); audit(db, principal, "survey_area.created", "survey_area", area.id, {"precision": area.precision}); db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "A collection with that name already exists")
    db.refresh(area); return dump(area)
@app.get("/v1/survey-areas")
def list_areas(db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))):
    areas = db.scalars(select(SurveyArea).order_by(SurveyArea.name)).all()
    run_counts = dict(db.execute(select(SurveyRun.survey_area_id, func.count(SurveyRun.id)).group_by(SurveyRun.survey_area_id)).all())
    device_counts = dict(db.execute(select(SurveyRun.survey_area_id, func.count(func.distinct(Observation.device_id))).join(Observation, Observation.survey_run_id == SurveyRun.id).group_by(SurveyRun.survey_area_id)).all())
    return [{**dump(x), "run_count": run_counts.get(x.id, 0), "device_count": device_counts.get(x.id, 0)} for x in areas]
@app.patch("/v1/survey-areas/{area_id}")
def rename_area(area_id: int, body: AreaPatch, db: Session = Depends(db_session), principal: Principal = Depends(protected("admin"))):
    area = db.get(SurveyArea, area_id)
    if not area: raise HTTPException(404, "Survey area not found")
    name = body.name.strip()
    if not name: raise HTTPException(422, "name must not be empty")
    if db.scalar(select(SurveyArea).where(SurveyArea.name == name, SurveyArea.id != area_id)): raise HTTPException(409, "Another collection already uses that name")
    previous = area.name
    area.name = name
    audit(db, principal, "survey_area.renamed", "survey_area", area.id, {"previous": previous, "name": name})
    try:
        db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "Another collection already uses that name")
    db.refresh(area)
    return dump(area)
@app.delete("/v1/survey-areas/{area_id}")
def delete_area(area_id: int, db: Session = Depends(db_session), principal: Principal = Depends(protected("admin"))):
    area = db.get(SurveyArea, area_id)
    if not area: raise HTTPException(404, "Survey area not found")
    if db.scalar(select(func.count()).select_from(SurveyRun).where(SurveyRun.survey_area_id == area_id)):
        raise HTTPException(409, "Delete or refile this collection's runs before deleting it")
    audit(db, principal, "survey_area.deleted", "survey_area", area.id, {"name": area.name})
    db.delete(area)
    db.commit()
    return {"status": "deleted", "area_id": area_id}
@app.post("/v1/survey-runs")
def create_run(body: RunInput, db: Session = Depends(db_session), principal: Principal = Depends(protected("analyst"))):
    if not db.get(SurveyArea, body.survey_area_id): raise HTTPException(404, "Survey area not found")
    run = SurveyRun(**body.model_dump()); db.add(run); db.flush(); audit(db, principal, "survey_run.created", "survey_run", run.id, {"area_id": run.survey_area_id}); db.commit(); db.refresh(run); return dump(run)
@app.get("/v1/survey-runs")
def list_runs(db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))): return [dump(x) for x in db.scalars(select(SurveyRun).order_by(SurveyRun.created_at.desc())).all()]
@app.post("/v1/survey-runs/{run_id}/complete")
def complete_run(run_id: int, db: Session = Depends(db_session), principal: Principal = Depends(protected("analyst"))):
    run = db.get(SurveyRun, run_id)
    if not run: raise HTTPException(404, "Survey run not found")
    run.completed = True; audit(db, principal, "survey_run.completed", "survey_run", run.id); db.commit(); return dump(run)
@app.delete("/v1/survey-runs/{run_id}")
def delete_run(run_id: int, db: Session = Depends(db_session), principal: Principal = Depends(protected("admin"))):
    run = db.get(SurveyRun, run_id)
    if not run: raise HTTPException(404, "Survey run not found")
    raw_paths = purge_run_data(db, run, principal)
    db.commit()
    for raw_path in raw_paths:
        try:
            if raw_path != "expired": Path(raw_path).unlink(missing_ok=True)
        except OSError: pass
    return {"status": "deleted", "run_id": run_id}

def retention_preview(db):
    raw_days = max(1, int(os.getenv("RAW_RETENTION_DAYS", "30")))
    normalized_days = max(1, int(os.getenv("NORMALIZED_RETENTION_DAYS", "365")))
    now = datetime.utcnow()
    raw_cutoff, normalized_cutoff = now - timedelta(days=raw_days), now - timedelta(days=normalized_days)
    raw_jobs = list(db.scalars(select(IngestionJob).where(IngestionJob.created_at < raw_cutoff, IngestionJob.raw_path != "expired").order_by(IngestionJob.created_at)).all())
    runs = list(db.scalars(select(SurveyRun).where(SurveyRun.created_at < normalized_cutoff).order_by(SurveyRun.created_at)).all())
    return {"raw_retention_days": raw_days, "normalized_retention_days": normalized_days, "raw_uploads": [{"id": job.id, "filename": job.filename, "created_at": job.created_at} for job in raw_jobs], "survey_runs": [{"id": run.id, "name": run.name, "created_at": run.created_at} for run in runs]}

@app.get("/v1/retention/preview")
def get_retention_preview(db: Session = Depends(db_session), principal: Principal = Depends(protected("admin"))):
    """Show retention candidates. This endpoint never modifies evidence."""
    return retention_preview(db)

@app.post("/v1/retention/purge")
def purge_retention(body: RetentionSweepInput, db: Session = Depends(db_session), principal: Principal = Depends(protected("admin"))):
    if body.confirm != "PURGE": raise HTTPException(422, "Set confirm to PURGE after reviewing the retention preview")
    preview = retention_preview(db)
    raw_paths = []
    removed_runs = []
    for item in preview["survey_runs"]:
        run = db.get(SurveyRun, item["id"])
        if run:
            raw_paths.extend(purge_run_data(db, run, principal, "retention.normalized_purged")); removed_runs.append(item["id"])
    for item in preview["raw_uploads"]:
        job = db.get(IngestionJob, item["id"])
        if job:
            raw_paths.append(job.raw_path); job.raw_path = "expired"
    audit(db, principal, "retention.swept", "retention", detail={"raw_uploads": len(preview["raw_uploads"]), "survey_runs": removed_runs, "raw_days": preview["raw_retention_days"], "normalized_days": preview["normalized_retention_days"]})
    db.commit()
    for raw_path in set(raw_paths):
        try:
            if raw_path != "expired": Path(raw_path).unlink(missing_ok=True)
        except OSError: pass
    return {"expired_raw_uploads": len(preview["raw_uploads"]), "purged_survey_runs": removed_runs}
@app.post("/v1/ingestions")
async def ingest(survey_run_id: int, source_format: str, file: UploadFile = File(...), db: Session = Depends(db_session), principal: Principal = Depends(protected("analyst"))):
    if source_format not in {"wigle", "kismet"}: raise HTTPException(422, "source_format must be wigle or kismet")
    if not db.get(SurveyRun, survey_run_id): raise HTTPException(404, "Survey run not found")
    filename = Path(file.filename or "upload").name
    if Path(filename).suffix.lower() not in ALLOWED_SUFFIXES: raise HTTPException(415, "Only CSV, JSON, NDJSON, and native Kismet uploads are allowed")
    blob = await file.read()
    if not blob or len(blob) > MAX_UPLOAD: raise HTTPException(413, "Upload must be 1 byte to 100 MB")
    digest = hashlib.sha256(blob).hexdigest(); old = db.scalar(select(IngestionJob).where(IngestionJob.file_hash == digest))
    if old: return {**dump(old), "idempotent": True}
    path = RAW / digest; path.write_bytes(blob)
    job = IngestionJob(survey_run_id=survey_run_id, filename=filename, source_format=source_format, file_hash=digest, raw_path=str(path))
    db.add(job); db.flush(); audit(db, principal, "ingestion.queued", "ingestion_job", job.id, {"source": source_format, "bytes": len(blob)}); db.commit(); db.refresh(job); queue.enqueue(process_ingestion, job.id, job_timeout=600); return job_view(job)

@app.post("/v1/imports")
async def quick_import(source_format: str = Form(...), file: UploadFile = File(...), session_name: str | None = Form(default=None), collection_name: str | None = Form(default=None), db: Session = Depends(db_session), principal: Principal = Depends(protected("analyst"))):
    """Create the organizing records only when a direct log upload needs them."""
    if source_format not in {"wigle", "kismet"}: raise HTTPException(422, "source_format must be wigle or kismet")
    blob = await file.read()
    if not blob or len(blob) > MAX_UPLOAD: raise HTTPException(413, "Upload must be 1 byte to 100 MB")
    digest = hashlib.sha256(blob).hexdigest(); old = db.scalar(select(IngestionJob).where(IngestionJob.file_hash == digest))
    if old: return {**job_view(old), "idempotent": True}
    file.file.seek(0)
    collection = (collection_name or "").strip()[:160]
    area = db.scalar(select(SurveyArea).where(SurveyArea.name == collection)) if collection else None
    if collection and not area:
        area = SurveyArea(name=collection, authorization_ref="operator-managed", purpose="Optional grouping for imported captures", precision="coarse")
        db.add(area); db.flush(); audit(db, principal, "collection.created", "collection", area.id, {"name": collection})
    stem = Path(file.filename or "capture").stem.strip() or "capture"
    generated_name = f"{stem[:110]} · {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    run = SurveyRun(survey_area_id=area.id if area else None, name=(session_name or generated_name).strip()[:160] or generated_name, authorization_ref="operator-managed", collector_coverage=1, completed=True)
    db.add(run); db.flush(); audit(db, principal, "import_session.created", "survey_run", run.id, {"collection": collection, "generated_name": not bool(session_name)})
    db.commit()
    return await ingest(run.id, source_format, file, db, principal)

@app.post("/v1/sessions/{session_id}/collection")
def assign_collection(session_id: int, body: CollectionAssignment, db: Session = Depends(db_session), principal: Principal = Depends(protected("analyst"))):
    session = db.get(SurveyRun, session_id)
    if not session: raise HTTPException(404, "Import session not found")
    name = body.name.strip()
    collection = db.scalar(select(SurveyArea).where(SurveyArea.name == name))
    if not collection:
        collection = SurveyArea(name=name, authorization_ref="operator-managed", purpose="Optional grouping for imported captures", precision="coarse")
        db.add(collection); db.flush(); audit(db, principal, "collection.created", "survey_area", collection.id, {"name": name})
    session.survey_area_id = collection.id
    audit(db, principal, "import_session.collected", "survey_run", session.id, {"collection": collection.name})
    db.commit()
    return dump(session)
@app.get("/v1/ingestions/{job_id}")
def get_ingestion(job_id: int, db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))):
    job = db.get(IngestionJob, job_id)
    if not job: raise HTTPException(404, "Ingestion not found")
    return job_view(job)
@app.get("/v1/ingestions/{job_id}/report")
def ingestion_report(job_id: int, db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))):
    job = db.get(IngestionJob, job_id)
    if not job: raise HTTPException(404, "Ingestion not found")
    report = job.report or {}
    lines = ["Signal Ledger ingestion report", f"File: {job.filename}", f"Source: {job.source_format}", f"Status: {job.status}", f"Parser version: {job.parser_version}"]
    lines += [f"{key}: {value}" for key, value in report.items() if key != "reasons"]
    for reason, number in (report.get("reasons") or {}).items(): lines.append(f"rejected.{reason}: {number}")
    return Response("\n".join(lines) + "\n", media_type="text/plain", headers={"Content-Disposition": f'attachment; filename="ingestion-{job.id}-report.txt"'})
@app.get("/v1/ingestions")
def list_ingestions(limit: int = Query(20, ge=1, le=100), db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))):
    return [job_view(item) for item in db.scalars(select(IngestionJob).order_by(IngestionJob.created_at.desc()).limit(limit)).all()]
@app.post("/v1/ingestions/{job_id}/retry")
def retry_ingestion(job_id: int, db: Session = Depends(db_session), principal: Principal = Depends(protected("admin"))):
    job = db.get(IngestionJob, job_id)
    if not job: raise HTTPException(404, "Ingestion not found")
    if job.report.get("accepted", 0) > 0: raise HTTPException(409, "Only zero-acceptance jobs can be retried safely")
    job.status = "queued"; job.report = {"retrying": True}; audit(db, principal, "ingestion.retried", "ingestion_job", job.id)
    db.commit(); queue.enqueue(process_ingestion, job.id, job_timeout=600)
    return job_view(job)
DEVICE_SORT_COLUMNS = {"last_seen": Device.last_seen, "first_seen": Device.first_seen, "oui_organization": Device.oui_organization, "category": Device.category}
@app.get("/v1/devices")
def devices(area_id: int | None = None, run_id: int | None = None, vendor: str | None = None, category: str | None = None, protocol: str | None = None, attributed_only: bool = False, sort: str = "last_seen", direction: str = "desc", start: datetime | None = None, end: datetime | None = None, min_quality: float | None = None, min_rssi: float | None = None, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))):
    if sort not in DEVICE_SORT_COLUMNS: raise HTTPException(422, "Unknown sort column")
    if direction not in {"asc", "desc"}: raise HTTPException(422, "direction must be asc or desc")
    query = select(Device)
    if vendor: query = query.where(Device.oui_organization.ilike(f"%{vendor}%"))
    if category: query = query.where(Device.category == category)
    if attributed_only: query = query.where(Device.oui_organization != "unattributable")
    observation_match = filtered_observations(select(Observation.id).join(SurveyRun).join(Device), area_id, run_id, protocol=protocol, start=start, end=end, min_quality=min_quality, min_rssi=min_rssi).where(Observation.device_id == Device.id)
    if any(value is not None for value in (area_id, run_id, protocol, start, end, min_quality, min_rssi)): query = query.where(observation_match.exists())
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    order_column = DEVICE_SORT_COLUMNS[sort]
    items = db.scalars(query.order_by(order_column.asc() if direction == "asc" else order_column.desc()).offset(offset).limit(limit)).all()
    device_ids = [item.id for item in items]
    last_seen_facts = {}
    if device_ids:
        for device_id, seen_protocol, ssid in db.execute(select(Observation.device_id, Observation.protocol, Observation.ssid).where(Observation.device_id.in_(device_ids)).order_by(Observation.captured_at.desc())):
            last_seen_facts.setdefault(device_id, {"last_protocol": seen_protocol, "last_ssid": ssid})
    return {"items": [{**device_view(x), **last_seen_facts.get(x.id, {"last_protocol": None, "last_ssid": None})} for x in items], "total": total, "limit": limit, "offset": offset}
@app.get("/v1/devices/vendors")
def device_vendor_summary(area_id: int | None = None, db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))):
    query = select(Device.oui_organization, func.count(Device.id)).group_by(Device.oui_organization)
    if area_id: query = query.where(Device.id.in_(select(Observation.device_id).join(SurveyRun).where(SurveyRun.survey_area_id == area_id)))
    rows = db.execute(query.order_by(func.count(Device.id).desc())).all()
    total = sum(count for _, count in rows) or 1
    return [{"oui_organization": name, "device_count": count, "share": round(count / total, 4)} for name, count in rows]
@app.get("/v1/devices/{device_id}")
def device_detail(device_id: int, limit: int = Query(100, ge=1, le=500), db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))):
    device = db.get(Device, device_id)
    if not device: raise HTTPException(404, "Device not found")
    records = db.execute(select(Observation, SurveyRun.name).join(SurveyRun).where(Observation.device_id == device_id).order_by(Observation.captured_at.desc()).limit(limit)).all()
    observation_count = db.scalar(select(func.count()).select_from(Observation).where(Observation.device_id == device_id))
    run_count = db.scalar(select(func.count(func.distinct(Observation.survey_run_id))).where(Observation.device_id == device_id))
    cells = db.scalar(select(func.count(func.distinct(Observation.spatial_cell))).where(Observation.device_id == device_id, Observation.spatial_cell.is_not(None)))
    # Device.collection_id is never populated by ingestion; a device's actual
    # collection(s) can only be derived by joining its observations' runs.
    collections = list(db.scalars(select(SurveyArea.name).join(SurveyRun, SurveyRun.survey_area_id == SurveyArea.id).join(Observation, Observation.survey_run_id == SurveyRun.id).where(Observation.device_id == device_id).distinct().order_by(SurveyArea.name)).all())
    return {"device": device_view(device), "summary": {"observations": observation_count, "runs": run_count, "coarse_cells": cells}, "collections": collections, "observations": [{**dump(item), "run_name": run_name} for item, run_name in records]}
@app.post("/v1/devices/{device_id}/reveal-address")
def reveal_device_address(device_id: int, db: Session = Depends(db_session), principal: Principal = Depends(protected("admin"))):
    device = db.get(Device, device_id)
    if not device: raise HTTPException(404, "Device not found")
    if not device.encrypted_address: raise HTTPException(409, "No stored address for this device")
    try: address = decrypt_address(device.encrypted_address)
    except ValueError as error: raise HTTPException(409, str(error))
    audit(db, principal, "device.address_revealed", "device", device.id); db.commit()
    return {"address": address}
@app.get("/v1/observations")
def observations(area_id: int | None = None, run_id: int | None = None, device_id: int | None = None, protocol: str | None = None, vendor: str | None = None, category: str | None = None, start: datetime | None = None, end: datetime | None = None, min_quality: float | None = None, min_rssi: float | None = None, limit: int = Query(500, ge=1, le=2000), db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))):
    query = filtered_observations(select(Observation).join(SurveyRun).join(Device), area_id, run_id, device_id, protocol, vendor, category, start, end, min_quality, min_rssi)
    return {"items": [dump(x) for x in db.scalars(query.order_by(Observation.captured_at.desc()).limit(limit)).all()], "limit": limit}
@app.get("/v1/map/clusters")
def map_clusters(area_id: int | None = None, run_id: int | None = None, device_id: int | None = None, protocol: str | None = None, vendor: str | None = None, category: str | None = None, start: datetime | None = None, end: datetime | None = None, min_quality: float | None = None, min_rssi: float | None = None, limit: int = Query(1000, ge=1, le=2000), db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))):
    query = filtered_observations(select(Observation.spatial_cell, func.count(Observation.id), func.avg(Observation.rssi), func.count(func.distinct(Observation.device_id))).join(SurveyRun).join(Device).where(Observation.spatial_cell.is_not(None), Observation.latitude.between(-90, 90), Observation.longitude.between(-180, 180), ~((Observation.latitude == 0) & (Observation.longitude == 0))), area_id, run_id, device_id, protocol, vendor, category, start, end, min_quality, min_rssi).group_by(Observation.spatial_cell)
    rows = db.execute(query.order_by(func.count(Observation.id).desc()).limit(limit))
    return [{"cell": row[0], "count": row[1], "avg_rssi": round(row[2], 1) if row[2] is not None else None, "device_count": row[3]} for row in rows]
@app.get("/v1/map/track")
def map_track(area_id: int | None = None, run_id: int | None = None, device_id: int | None = None, protocol: str | None = None, vendor: str | None = None, category: str | None = None, start: datetime | None = None, end: datetime | None = None, min_quality: float | None = None, min_rssi: float | None = None, limit: int = Query(5000, ge=1, le=10000), db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))):
    """Return coarse sensor movement segments, never exact points or device locations."""
    query = filtered_observations(select(Observation.survey_run_id, Observation.captured_at, Observation.latitude, Observation.longitude).join(SurveyRun).join(Device).where(Observation.latitude.between(-90, 90), Observation.longitude.between(-180, 180), ~((Observation.latitude == 0) & (Observation.longitude == 0))), area_id, run_id, device_id, protocol, vendor, category, start, end, min_quality, min_rssi)
    segments, current, previous, records = [], [], None, 0
    for item in db.execute(query.order_by(Observation.captured_at).limit(limit)):
        records += 1
        run, captured, latitude, longitude = item
        cell = f"{round(latitude, 3):.3f},{round(longitude, 3):.3f}"
        boundary = previous and (run != previous[0] or (captured - previous[1]).total_seconds() > 300)
        if boundary and current: segments.append(current); current = []
        if not current or current[-1]["cell"] != cell: current.append({"cell": cell, "captured_at": captured})
        previous = (run, captured)
    if current: segments.append(current)
    return {"segments": segments, "truncated": records >= limit}
@app.get("/v1/analytics/discovery")
def analytics(area_id: int | None = None, run_id: int | None = None, device_id: int | None = None, protocol: str | None = None, vendor: str | None = None, category: str | None = None, start: datetime | None = None, end: datetime | None = None, min_quality: float | None = None, min_rssi: float | None = None, db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))):
    base = lambda fields: filtered_observations(select(*fields).join(SurveyRun).join(Device), area_id, run_id, device_id, protocol, vendor, category, start, end, min_quality, min_rssi)
    protocol_mix = {name: total for name, total in db.execute(base([Observation.protocol, func.count(Observation.id)]).group_by(Observation.protocol))}
    category_mix = {name: total for name, total in db.execute(base([Device.category, func.count(Observation.id)]).group_by(Device.category))}
    vendor_mix = {name: total for name, total in db.execute(base([Device.oui_organization, func.count(Observation.id)]).group_by(Device.oui_organization).order_by(func.count(Observation.id).desc()).limit(12))}
    daily = [{"day": str(day), "count": total} for day, total in db.execute(base([func.date(Observation.captured_at), func.count(Observation.id)]).group_by(func.date(Observation.captured_at)).order_by(func.date(Observation.captured_at)))]
    mean_quality = db.scalar(base([func.avg(Observation.quality)])) or 0
    return {"protocol_mix": protocol_mix, "category_mix": category_mix, "vendor_mix": vendor_mix, "daily_observations": daily, "mean_quality": round(mean_quality, 2)}
@app.post("/v1/baselines")
def create_baseline(body: BaselineInput, db: Session = Depends(db_session), principal: Principal = Depends(protected("analyst"))):
    area = db.get(SurveyArea, body.survey_area_id)
    if not area: raise HTTPException(404, "Survey area not found")
    runs = db.scalars(select(SurveyRun).where(SurveyRun.id.in_(body.run_ids), SurveyRun.survey_area_id == area.id)).all()
    if len(runs) != len(set(body.run_ids)): raise HTTPException(422, "Every selected run must belong to this area")
    if any(not run.completed for run in runs): raise HTTPException(422, "Complete selected runs before freezing a baseline")
    baseline = Baseline(survey_area_id=area.id, name=body.name, run_ids=sorted(set(body.run_ids)), expectations=baseline_expectations(db, area.id, body.run_ids))
    db.add(baseline); db.flush(); build_anomalies(db, baseline); audit(db, principal, "baseline.created", "baseline", baseline.id, {"runs": baseline.run_ids, "rule_version": baseline.expectations["version"]}); db.commit(); db.refresh(baseline)
    return dump(baseline)
@app.get("/v1/baselines")
def list_baselines(area_id: int | None = None, db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))):
    query = select(Baseline).order_by(Baseline.created_at.desc())
    if area_id: query = query.where(Baseline.survey_area_id == area_id)
    return [dump(item) for item in db.scalars(query).all()]
@app.post("/v1/baselines/{baseline_id}/evaluate")
def evaluate_baseline(baseline_id: int, db: Session = Depends(db_session), principal: Principal = Depends(protected("analyst"))):
    baseline = db.get(Baseline, baseline_id)
    if not baseline: raise HTTPException(404, "Baseline not found")
    build_anomalies(db, baseline); audit(db, principal, "baseline.evaluated", "baseline", baseline.id); db.commit()
    return {"baseline_id": baseline.id, "findings": db.scalar(select(func.count()).select_from(Anomaly).where(Anomaly.baseline_id == baseline.id))}
@app.get("/v1/anomalies")
def list_anomalies(area_id: int | None = None, baseline_id: int | None = None, status: str | None = None, db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))):
    query = select(Anomaly).order_by(Anomaly.score.desc(), Anomaly.created_at.desc())
    if area_id: query = query.where(Anomaly.survey_area_id == area_id)
    if baseline_id: query = query.where(Anomaly.baseline_id == baseline_id)
    if status: query = query.where(Anomaly.status == status)
    return [dump(item) for item in db.scalars(query).all()]
@app.patch("/v1/anomalies/{anomaly_id}")
def update_anomaly(anomaly_id: int, body: AnomalyPatch, db: Session = Depends(db_session), principal: Principal = Depends(protected("analyst"))):
    if body.status not in {"open", "dismissed", "confirmed", "needs_review"}: raise HTTPException(422, "Unknown anomaly status")
    item = db.get(Anomaly, anomaly_id)
    if not item: raise HTTPException(404, "Anomaly not found")
    item.status = body.status; item.disposition_note = body.disposition_note; audit(db, principal, "anomaly.disposition", "anomaly", item.id, {"status": item.status}); db.commit(); return dump(item)
@app.post("/v1/saved-filters")
def save_filter(body: FilterInput, db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))):
    item = SavedFilter(name=body.name, owner=principal.actor, resource=body.resource, filters=body.filters); db.add(item); db.flush(); audit(db, principal, "filter.saved", "saved_filter", item.id); db.commit(); return dump(item)
@app.get("/v1/saved-filters")
def list_filters(db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))): return [dump(x) for x in db.scalars(select(SavedFilter).where(SavedFilter.owner == principal.actor).order_by(SavedFilter.created_at.desc())).all()]
@app.get("/v1/audit-events")
def audit_events(limit: int = Query(100, ge=1, le=500), db: Session = Depends(db_session), principal: Principal = Depends(protected("auditor"))): return [dump(x) for x in db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)).all()]
