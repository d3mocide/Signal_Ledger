"""Minimal, idempotent schema migration runner for the modular-monolith MVP."""
from sqlalchemy import text
from .database import Base, engine

MIGRATIONS = [
    ("0001_postgis", "CREATE EXTENSION IF NOT EXISTS postgis"),
    ("0002_observation_geom", "ALTER TABLE observations ADD COLUMN IF NOT EXISTS geom geometry(Point, 4326)"),
    ("0003_observation_geom_index", "CREATE INDEX IF NOT EXISTS ix_observations_geom ON observations USING GIST (geom)"),
    ("0004_device_encrypted_address", "ALTER TABLE devices ADD COLUMN IF NOT EXISTS encrypted_address varchar(255)"),
    ("0005_category_evidence", "ALTER TABLE devices ADD COLUMN IF NOT EXISTS category_evidence json NOT NULL DEFAULT '[]'::json; ALTER TABLE devices ADD COLUMN IF NOT EXISTS category_overridden boolean NOT NULL DEFAULT false"),
    ("0006_anomaly_evidence_links", "ALTER TABLE anomalies ADD COLUMN IF NOT EXISTS evidence_links json NOT NULL DEFAULT '[]'::json"),
    ("0007_workspace_settings", "CREATE TABLE IF NOT EXISTS workspace_settings (id integer primary key, raw_retention_days integer NOT NULL DEFAULT 30, normalized_retention_days integer NOT NULL DEFAULT 365, updated_by varchar(120), updated_at timestamp NOT NULL DEFAULT now())"),
    ("0008_category_scores", "ALTER TABLE devices ADD COLUMN IF NOT EXISTS category_scores json NOT NULL DEFAULT '{}'::json; ALTER TABLE devices ADD COLUMN IF NOT EXISTS category_rule_version varchar(32) NOT NULL DEFAULT 'rules-v2'"),
    ("0009_raw_storage_encryption", "ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS raw_encrypted boolean NOT NULL DEFAULT false"),
    ("0010_observation_device_signals", "ALTER TABLE devices ADD COLUMN IF NOT EXISTS address_scope varchar(32) NOT NULL DEFAULT 'unknown'; ALTER TABLE observations ADD COLUMN IF NOT EXISTS device_name varchar(160); ALTER TABLE observations ADD COLUMN IF NOT EXISTS device_type varchar(120)"),
    ("0011_device_roles", "ALTER TABLE devices ADD COLUMN IF NOT EXISTS device_roles json NOT NULL DEFAULT '[]'::json; ALTER TABLE devices ADD COLUMN IF NOT EXISTS role_scores json NOT NULL DEFAULT '{}'::json; ALTER TABLE devices ADD COLUMN IF NOT EXISTS role_evidence json NOT NULL DEFAULT '[]'::json; ALTER TABLE devices ADD COLUMN IF NOT EXISTS role_rule_version varchar(32) NOT NULL DEFAULT 'roles-v1'"),
    ("0012_device_reviews", "CREATE TABLE IF NOT EXISTS device_reviews (id integer primary key, device_id integer NOT NULL UNIQUE REFERENCES devices(id), status varchar(24) NOT NULL DEFAULT 'open', disposition_note text, evidence_links json NOT NULL DEFAULT '[]'::json, reviewed_by varchar(120), reviewed_at timestamp, created_at timestamp NOT NULL DEFAULT now()); CREATE INDEX IF NOT EXISTS ix_device_reviews_device_id ON device_reviews(device_id); CREATE INDEX IF NOT EXISTS ix_device_reviews_status ON device_reviews(status)"),
]

def upgrade():
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version varchar(64) primary key, applied_at timestamp default now())"))
        applied = {row[0] for row in connection.execute(text("SELECT version FROM schema_migrations"))}
        for version, sql in MIGRATIONS:
            if version not in applied:
                connection.execute(text(sql))
                connection.execute(text("INSERT INTO schema_migrations(version) VALUES (:version)"), {"version": version})
