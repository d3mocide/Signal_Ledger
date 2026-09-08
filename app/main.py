import hashlib, os, time
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from redis import Redis
from rq import Queue
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from .database import SessionLocal
from .migrations import upgrade
from .models import AuditEvent, Device, IngestionJob, LoginSession, Observation, SavedFilter, SurveyArea, SurveyRun, User
from .security import Principal, ROLE_ORDER, ROLES, SESSION_COOKIE, authenticate, expires_at, password_hash, password_valid, session_token, token_hash
from .tasks import process_ingestion

RAW = Path(os.getenv("RAW_STORAGE_PATH", "/tmp/signal-ledger/raw")); RAW.mkdir(parents=True, exist_ok=True)
redis = Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0")); queue = Queue("signal-ledger", connection=redis)
MAX_UPLOAD = 100 * 1024 * 1024; ALLOWED_SUFFIXES = {".csv", ".json", ".ndjson"}
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
    request.state.db = SessionLocal()
    try: return await call_next(request)
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
def ensure(principal, minimum):
    if ROLE_ORDER[principal.role] < ROLE_ORDER[minimum]: raise HTTPException(403, f"{minimum} role required")
def audit(db, principal, action, resource_type, resource_id=None, detail=None):
    db.add(AuditEvent(actor=principal.actor, role=principal.role, action=action, resource_type=resource_type, resource_id=str(resource_id) if resource_id else None, detail=detail or {}))
def protected(minimum):
    def dependency(principal: Principal = Depends(authenticate)):
        ensure(principal, minimum); return principal
    return dependency
class AreaInput(BaseModel):
    name: str = Field(max_length=160); authorization_ref: str = Field(max_length=240); purpose: str = Field(default="asset awareness", max_length=2000); precision: str = "coarse"; polygon: dict | None = None
class RunInput(BaseModel):
    survey_area_id: int; name: str = Field(max_length=160); authorization_ref: str = Field(max_length=240); collector_coverage: float = Field(1, ge=0, le=1)
class FilterInput(BaseModel):
    name: str = Field(max_length=120); resource: str = "observations"; filters: dict
class Credentials(BaseModel):
    username: str = Field(pattern=r"^[a-zA-Z0-9_.-]{3,80}$"); password: str = Field(min_length=10, max_length=256)
class UserInput(Credentials):
    role: str

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
def me(principal: Principal = Depends(authenticate)): return {"actor": principal.actor, "role": principal.role}
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
@app.get("/v1/overview")
def overview(db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))):
    count = lambda table: db.scalar(select(func.count()).select_from(table))
    return {"areas": count(SurveyArea), "runs": count(SurveyRun), "observations": count(Observation), "devices": count(Device), "unattributable": db.scalar(select(func.count()).select_from(Device).where(Device.oui_organization == "unattributable")), "completed_runs": db.scalar(select(func.count()).select_from(SurveyRun).where(SurveyRun.completed == True))}
@app.post("/v1/survey-areas")
def create_area(body: AreaInput, db: Session = Depends(db_session), principal: Principal = Depends(protected("analyst"))):
    if body.precision not in {"coarse", "exact"}: raise HTTPException(422, "precision must be coarse or exact")
    area = SurveyArea(**body.model_dump()); db.add(area); db.flush(); audit(db, principal, "survey_area.created", "survey_area", area.id, {"precision": area.precision}); db.commit(); db.refresh(area); return dump(area)
@app.get("/v1/survey-areas")
def list_areas(db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))): return [dump(x) for x in db.scalars(select(SurveyArea).order_by(SurveyArea.name)).all()]
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
@app.post("/v1/ingestions")
async def ingest(survey_run_id: int, source_format: str, file: UploadFile = File(...), db: Session = Depends(db_session), principal: Principal = Depends(protected("analyst"))):
    if source_format not in {"wigle", "kismet"}: raise HTTPException(422, "source_format must be wigle or kismet")
    if not db.get(SurveyRun, survey_run_id): raise HTTPException(404, "Survey run not found")
    filename = Path(file.filename or "upload").name
    if Path(filename).suffix.lower() not in ALLOWED_SUFFIXES: raise HTTPException(415, "Only CSV, JSON, and NDJSON uploads are allowed")
    blob = await file.read()
    if not blob or len(blob) > MAX_UPLOAD: raise HTTPException(413, "Upload must be 1 byte to 100 MB")
    digest = hashlib.sha256(blob).hexdigest(); old = db.scalar(select(IngestionJob).where(IngestionJob.file_hash == digest))
    if old: return {**dump(old), "idempotent": True}
    path = RAW / digest; path.write_bytes(blob)
    job = IngestionJob(survey_run_id=survey_run_id, filename=filename, source_format=source_format, file_hash=digest, raw_path=str(path))
    db.add(job); db.flush(); audit(db, principal, "ingestion.queued", "ingestion_job", job.id, {"source": source_format, "bytes": len(blob)}); db.commit(); db.refresh(job); queue.enqueue(process_ingestion, job.id, job_timeout=600); return job_view(job)
@app.get("/v1/ingestions/{job_id}")
def get_ingestion(job_id: int, db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))):
    job = db.get(IngestionJob, job_id)
    if not job: raise HTTPException(404, "Ingestion not found")
    return job_view(job)
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
@app.get("/v1/devices")
def devices(area_id: int | None = None, vendor: str | None = None, category: str | None = None, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))):
    query = select(Device).order_by(Device.last_seen.desc()).offset(offset).limit(limit)
    if area_id: query = query.where(Device.survey_area_id == area_id)
    if vendor: query = query.where(Device.oui_organization.ilike(f"%{vendor}%"))
    if category: query = query.where(Device.category == category)
    return {"items": [dump(x) for x in db.scalars(query).all()], "limit": limit, "offset": offset}
@app.get("/v1/observations")
def observations(area_id: int | None = None, protocol: str | None = None, start: datetime | None = None, end: datetime | None = None, min_quality: float | None = Query(None, ge=0, le=1), limit: int = Query(500, ge=1, le=2000), db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))):
    query = select(Observation).join(SurveyRun).order_by(Observation.captured_at.desc()).limit(limit)
    if area_id: query = query.where(SurveyRun.survey_area_id == area_id)
    if protocol: query = query.where(Observation.protocol == protocol)
    if start: query = query.where(Observation.captured_at >= start)
    if end: query = query.where(Observation.captured_at <= end)
    if min_quality is not None: query = query.where(Observation.quality >= min_quality)
    return {"items": [dump(x) for x in db.scalars(query).all()], "limit": limit}
@app.get("/v1/map/clusters")
def map_clusters(area_id: int | None = None, run_id: int | None = None, device_id: int | None = None, protocol: str | None = None, limit: int = Query(1000, ge=1, le=2000), db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))):
    query = select(Observation.spatial_cell, func.count(Observation.id), func.avg(Observation.rssi), func.count(func.distinct(Observation.device_id))).join(SurveyRun).where(Observation.spatial_cell.is_not(None)).group_by(Observation.spatial_cell)
    if area_id: query = query.where(SurveyRun.survey_area_id == area_id)
    if run_id: query = query.where(Observation.survey_run_id == run_id)
    if device_id: query = query.where(Observation.device_id == device_id)
    if protocol: query = query.where(Observation.protocol == protocol)
    rows = db.execute(query.order_by(func.count(Observation.id).desc()).limit(limit))
    return [{"cell": row[0], "count": row[1], "avg_rssi": round(row[2], 1) if row[2] is not None else None, "device_count": row[3]} for row in rows]
@app.get("/v1/analytics/discovery")
def analytics(area_id: int | None = None, run_id: int | None = None, device_id: int | None = None, db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))):
    query = select(Observation).join(SurveyRun)
    if area_id: query = query.where(SurveyRun.survey_area_id == area_id)
    if run_id: query = query.where(Observation.survey_run_id == run_id)
    if device_id: query = query.where(Observation.device_id == device_id)
    rows = db.scalars(query).all(); protocol = Counter(item.protocol for item in rows); days = Counter(item.captured_at.date().isoformat() for item in rows)
    return {"protocol_mix": protocol, "daily_observations": [{"day": day, "count": count} for day, count in sorted(days.items())], "mean_quality": round(sum(item.quality for item in rows) / len(rows), 2) if rows else 0}
@app.post("/v1/saved-filters")
def save_filter(body: FilterInput, db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))):
    item = SavedFilter(name=body.name, owner=principal.actor, resource=body.resource, filters=body.filters); db.add(item); db.flush(); audit(db, principal, "filter.saved", "saved_filter", item.id); db.commit(); return dump(item)
@app.get("/v1/saved-filters")
def list_filters(db: Session = Depends(db_session), principal: Principal = Depends(protected("viewer"))): return [dump(x) for x in db.scalars(select(SavedFilter).where(SavedFilter.owner == principal.actor).order_by(SavedFilter.created_at.desc())).all()]
@app.get("/v1/audit-events")
def audit_events(limit: int = Query(100, ge=1, le=500), db: Session = Depends(db_session), principal: Principal = Depends(protected("auditor"))): return [dump(x) for x in db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)).all()]
