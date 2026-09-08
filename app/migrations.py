"""Minimal, idempotent schema migration runner for the modular-monolith MVP."""
from sqlalchemy import text
from .database import Base, engine

MIGRATIONS = [
    ("0001_postgis", "CREATE EXTENSION IF NOT EXISTS postgis"),
    ("0002_observation_geom", "ALTER TABLE observations ADD COLUMN IF NOT EXISTS geom geometry(Point, 4326)"),
    ("0003_observation_geom_index", "CREATE INDEX IF NOT EXISTS ix_observations_geom ON observations USING GIST (geom)"),
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
