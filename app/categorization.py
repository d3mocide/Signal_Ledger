"""Bounded category rebuilds for devices imported before a rule-set change."""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Device, Observation
from .policies import CATEGORY_RULE_VERSION, ROLE_RULE_VERSION, category_from_scores, category_scores, device_role_scores, device_roles_from_scores


def rebuild_categories(db: Session, limit: int = 5000) -> tuple[int, int]:
    """Re-evaluate a bounded device batch without changing analyst overrides."""
    devices = list(db.scalars(select(Device).order_by(Device.id).limit(limit)).all())
    if not devices:
        return 0, 0
    device_ids = [device.id for device in devices]
    aggregates: dict[int, dict[str, float]] = defaultdict(dict)
    evidence: dict[int, list[str]] = defaultdict(list)
    role_aggregates: dict[int, dict[str, float]] = defaultdict(dict)
    role_evidence: dict[int, list[str]] = defaultdict(list)
    rows = db.execute(select(Observation, Device).join(Device).where(Device.id.in_(device_ids))).all()
    for observation, device in rows:
        scores, facts = category_scores(device.oui_organization, observation.ssid, observation.protocol, observation.device_name, observation.device_type, device.address_scope)
        observed_roles, observed_role_evidence = device_role_scores(device.oui_organization, observation.ssid, observation.protocol, observation.device_name, observation.device_type)
        for category, score in scores.items():
            aggregates[device.id][category] = min(20.0, aggregates[device.id].get(category, 0) + score)
        for fact in facts:
            if fact not in evidence[device.id]:
                evidence[device.id].append(fact)
        for role, score in observed_roles.items():
            role_aggregates[device.id][role] = min(20.0, role_aggregates[device.id].get(role, 0) + score)
        for fact in observed_role_evidence:
            if fact not in role_evidence[device.id]:
                role_evidence[device.id].append(fact)
    updated = overridden = 0
    for device in devices:
        device.category_rule_version = CATEGORY_RULE_VERSION
        device.category_scores = {key: round(value, 3) for key, value in aggregates.get(device.id, {}).items()}
        device.category_evidence = evidence.get(device.id, ["unknown: no retained observation matched a configured rule"])[:12]
        device.role_rule_version = ROLE_RULE_VERSION
        device.role_scores = {key: round(value, 3) for key, value in role_aggregates.get(device.id, {}).items()}
        device.device_roles = device_roles_from_scores(device.role_scores)
        device.role_evidence = role_evidence.get(device.id, [])[:12]
        if device.category_overridden:
            overridden += 1
            continue
        device.category, device.category_confidence, _ = category_from_scores(device.category_scores, device.category_evidence)
        updated += 1
    return updated, overridden
