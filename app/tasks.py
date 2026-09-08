import hashlib, hmac, os
from sqlalchemy import select
from .database import SessionLocal
from .models import IngestionJob, SurveyRun, Device, Observation, AuditEvent
from .oui import vendor_for
from .parsers import PARSER_VERSION, parse

HMAC_SECRET = os.getenv("HMAC_SECRET", "development-only-replace-me").encode()
def _cell(lat, lon): return f"{round(lat,3):.3f},{round(lon,3):.3f}" if lat is not None and lon is not None else None

def process_ingestion(job_id: int):
    db = SessionLocal()
    try:
        job = db.get(IngestionJob, job_id)
        if not job or job.status == "complete": return
        job.status = "processing"; db.commit()
        run = db.get(SurveyRun, job.survey_run_id)
        accepted = rejected = skipped = 0; reasons = {}; seen = set(); valid = []
        for line, parsed, error in parse(job.raw_path, job.source_format):
            if error:
                rejected += 1; reasons[error] = reasons.get(error, 0) + 1; continue
            normalized = parsed.address.replace(":", "").replace("-", "").upper()
            prefix = None if int(normalized[:2], 16) & 2 else normalized[:6]
            token = hmac.new(HMAC_SECRET, f"{run.survey_area_id}:{normalized}".encode(), hashlib.sha256).hexdigest()
            key = (token, parsed.captured_at, parsed.protocol, parsed.ssid, _cell(parsed.latitude, parsed.longitude))
            if key in seen: skipped += 1; continue
            seen.add(key)
            valid.append((line, parsed, prefix, token))
        # Load the area inventory once, then flush in two bounded phases. This
        # avoids a select/flush/update round-trip for every row in a wardrive.
        devices = {item.token: item for item in db.scalars(select(Device).where(Device.survey_area_id == run.survey_area_id)).all()}
        for _, parsed, prefix, token in valid:
            device = devices.get(token)
            if not device:
                device = Device(survey_area_id=run.survey_area_id, token=token, oui_prefix=prefix, oui_organization=vendor_for(prefix), first_seen=parsed.captured_at, last_seen=parsed.captured_at)
                db.add(device); devices[token] = device
            else:
                device.first_seen = min(device.first_seen, parsed.captured_at); device.last_seen = max(device.last_seen, parsed.captured_at)
        db.flush()
        db.add_all([Observation(survey_run_id=run.id, ingestion_job_id=job.id, device_id=devices[token].id, captured_at=parsed.captured_at, protocol=parsed.protocol, ssid=parsed.ssid, security=parsed.security, rssi=parsed.rssi, latitude=parsed.latitude, longitude=parsed.longitude, spatial_cell=_cell(parsed.latitude, parsed.longitude), quality=1.0 if parsed.latitude is not None else .65, source_row=line) for line, parsed, _, token in valid])
        accepted = len(valid)
        job.status = "complete"; job.parser_version = PARSER_VERSION; job.report = {"accepted": accepted, "rejected": rejected, "skipped_duplicates": skipped, "reasons": reasons, "parser_version": PARSER_VERSION, "source": job.source_format, "coverage": run.collector_coverage}
        db.add(AuditEvent(actor="worker", role="system", action="ingestion.completed", resource_type="ingestion_job", resource_id=str(job.id), detail=job.report))
        db.commit()
    except Exception as exc:
        db.rollback(); job = db.get(IngestionJob, job_id)
        if job: job.status = "failed"; job.report = {"error": str(exc)[:300], "parser_version": "v1"}; db.commit()
        raise
    finally: db.close()
