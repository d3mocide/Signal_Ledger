import hashlib, hmac, logging, os
from sqlalchemy import select, text
from .crypto import encrypt_address
from .database import SessionLocal
from .models import IngestionJob, SurveyRun, SurveyArea, Device, Observation, AuditEvent, OUIAssignment
from .oui import vendor_for
from .parsers import PARSER_VERSION, parse
from .policies import CATEGORY_RULE_VERSION, ROLE_RULE_VERSION, category_from_scores, category_scores, device_role_scores, device_roles_from_scores, mac_address_scope, point_in_polygon
from .raw_storage import materialize_raw
from .observability import configure_logging, event

HMAC_SECRET = os.getenv("HMAC_SECRET", "development-only-replace-me").encode()
configure_logging()
logger = logging.getLogger("signal_ledger")


def device_token(normalized_address: str, secret: bytes | None = None) -> str:
    return hmac.new(secret if secret is not None else HMAC_SECRET, normalized_address.encode(), hashlib.sha256).hexdigest()

def _cell(lat, lon):
    return f"{round(lat,3):.3f},{round(lon,3):.3f}" if lat is not None and lon is not None and not (lat == 0 and lon == 0) else None

def process_ingestion(job_id: int):
    db = SessionLocal()
    try:
        job = db.get(IngestionJob, job_id)
        if not job or job.status == "complete": return
        job.status = "processing"; db.commit()
        run = db.get(SurveyRun, job.survey_run_id)
        area = db.get(SurveyArea, run.survey_area_id) if run.survey_area_id else None
        exact_area = bool(area and area.precision == "exact")
        accepted = rejected = skipped = 0; reasons = {}; seen = set(); valid = []
        with materialize_raw(job.raw_path, bool(job.raw_encrypted)) as source_path:
            for line, parsed, error in parse(source_path, job.source_format):
                if error:
                    rejected += 1; reasons[error] = reasons.get(error, 0) + 1; continue
                if area and area.polygon and parsed.latitude is not None and parsed.longitude is not None and not point_in_polygon(parsed.latitude, parsed.longitude, area.polygon):
                    rejected += 1; reasons["outside_area_polygon"] = reasons.get("outside_area_polygon", 0) + 1; continue
                normalized = parsed.address.replace(":", "").replace("-", "").upper()
                address_scope = mac_address_scope(parsed.address)
                prefix = normalized[:6] if address_scope == "globally_administered" else None
                token = device_token(normalized)
                key = (token, parsed.captured_at, parsed.protocol, parsed.ssid, _cell(parsed.latitude, parsed.longitude))
                if key in seen: skipped += 1; continue
                seen.add(key)
                valid.append((line, parsed, prefix, token, normalized))
        # Load the area inventory once, then flush in two bounded phases. This
        # avoids a select/flush/update round-trip for every row in a wardrive.
        devices = {item.token: item for item in db.scalars(select(Device)).all()}
        oui_catalog = {item.prefix: item.organization for item in db.scalars(select(OUIAssignment)).all()}
        for _, parsed, prefix, token, normalized in valid:
            device = devices.get(token)
            address_scope = mac_address_scope(parsed.address)
            vendor = oui_catalog.get(prefix, vendor_for(prefix))
            observed_scores, observed_evidence = category_scores(vendor, parsed.ssid, parsed.protocol, parsed.device_name, parsed.device_type, address_scope)
            observed_role_scores, observed_role_evidence = device_role_scores(vendor, parsed.ssid, parsed.protocol, parsed.device_name, parsed.device_type)
            if not device:
                category, confidence, evidence = category_from_scores(observed_scores, observed_evidence)
                device = Device(token=token, oui_prefix=prefix, oui_organization=vendor, category=category, category_confidence=confidence, category_evidence=evidence, category_scores=observed_scores, category_rule_version=CATEGORY_RULE_VERSION, device_roles=device_roles_from_scores(observed_role_scores), role_scores=observed_role_scores, role_evidence=observed_role_evidence[:12], role_rule_version=ROLE_RULE_VERSION, address_scope=address_scope, first_seen=parsed.captured_at, last_seen=parsed.captured_at)
                if exact_area: device.encrypted_address = encrypt_address(normalized)
                db.add(device); devices[token] = device
            else:
                device.first_seen = min(device.first_seen, parsed.captured_at); device.last_seen = max(device.last_seen, parsed.captured_at)
                if exact_area and not device.encrypted_address: device.encrypted_address = encrypt_address(normalized)
                if device.address_scope == "unknown": device.address_scope = address_scope
                aggregate_scores = dict(device.category_scores or {})
                for key, value in observed_scores.items(): aggregate_scores[key] = round(min(20.0, aggregate_scores.get(key, 0) + value), 3)
                device.category_scores = aggregate_scores
                device.category_rule_version = CATEGORY_RULE_VERSION
                aggregate_role_scores = dict(device.role_scores or {})
                for key, value in observed_role_scores.items(): aggregate_role_scores[key] = round(min(20.0, aggregate_role_scores.get(key, 0) + value), 3)
                device.role_scores = aggregate_role_scores
                device.device_roles = device_roles_from_scores(aggregate_role_scores)
                device.role_rule_version = ROLE_RULE_VERSION
                category, confidence, _ = category_from_scores(aggregate_scores, device.category_evidence or [])
                if not device.category_overridden:
                    device.category, device.category_confidence = category, confidence
                current_evidence = list(device.category_evidence or [])
                for item in observed_evidence:
                    if item not in current_evidence: current_evidence.append(item)
                device.category_evidence = current_evidence[:12]
                current_role_evidence = list(device.role_evidence or [])
                for item in observed_role_evidence:
                    if item not in current_role_evidence: current_role_evidence.append(item)
                device.role_evidence = current_role_evidence[:12]
        db.flush()
        db.add_all([Observation(survey_run_id=run.id, ingestion_job_id=job.id, device_id=devices[token].id, captured_at=parsed.captured_at, protocol=parsed.protocol, ssid=parsed.ssid, device_name=parsed.device_name, device_type=parsed.device_type, security=parsed.security, rssi=parsed.rssi, latitude=parsed.latitude, longitude=parsed.longitude, spatial_cell=_cell(parsed.latitude, parsed.longitude), quality=1.0 if parsed.latitude is not None else .65, source_row=line) for line, parsed, _, token, _ in valid])
        db.flush()
        # The UI remains coarse-cell by default; PostGIS geometry is retained
        # only for policy-approved spatial queries and indexed by the migration.
        db.execute(text("UPDATE observations SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326) WHERE ingestion_job_id = :job_id AND latitude IS NOT NULL AND longitude IS NOT NULL"), {"job_id": job.id})
        accepted = len(valid)
        located = sum(1 for _, parsed, _, _, _ in valid if parsed.latitude is not None and parsed.longitude is not None)
        run.completed = True
        job.status = "complete"; job.parser_version = PARSER_VERSION; job.report = {"accepted": accepted, "rejected": rejected, "skipped_duplicates": skipped, "reasons": reasons, "parser_version": PARSER_VERSION, "source": job.source_format, "coverage": run.collector_coverage, "location_present": located, "location_completeness": round(located / accepted, 3) if accepted else 0}
        db.add(AuditEvent(actor="worker", role="system", action="ingestion.completed", resource_type="ingestion_job", resource_id=str(job.id), detail=job.report))
        db.commit()
        event(logger, "ingestion.completed", job_id=job.id, source=job.source_format, accepted=accepted, rejected=rejected, skipped=skipped)
    except Exception as exc:
        db.rollback(); job = db.get(IngestionJob, job_id)
        if job: job.status = "failed"; job.report = {"error": str(exc)[:300], "parser_version": "v1"}; db.commit()
        event(logger, "ingestion.failed", job_id=job_id, error_type=type(exc).__name__)
        raise
    finally: db.close()
