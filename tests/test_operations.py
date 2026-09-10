import json
from contextlib import contextmanager

import app.main as main_module
from app.observability import safe_fields
from app.tasks import device_token


def test_structured_log_fields_redact_sensitive_values():
    fields = safe_fields({"job_id": 7, "accepted": 12, "raw_path": "/private/capture.csv", "hmac_secret": "never-log"})
    assert fields == {"job_id": 7, "accepted": 12}


def test_hmac_token_epochs_are_distinct_without_exposing_the_secret():
    address = "001122334455"
    assert device_token(address, b"first-disposable-epoch") != device_token(address, b"second-disposable-epoch")


def test_health_reports_dependency_status_without_database_details(monkeypatch):
    class BrokenEngine:
        def connect(self):
            raise RuntimeError("database unavailable")

    class AvailableRedis:
        def ping(self):
            return True

    class Worker:
        @staticmethod
        def all(connection):
            return []

    monkeypatch.setattr(main_module, "engine", BrokenEngine())
    monkeypatch.setattr(main_module, "redis", AvailableRedis())
    monkeypatch.setattr(main_module, "Worker", Worker)

    response = main_module.health()
    body = json.loads(response.body)
    assert response.status_code == 503
    assert body["status"] == "degraded"
    assert body["components"] == {"database": False, "redis": True, "worker": False}
    assert "database unavailable" not in response.body.decode()


def test_health_is_ok_only_when_database_and_redis_are_reachable(monkeypatch):
    class Connection:
        def execute(self, statement):
            assert str(statement) == "SELECT 1"

    class Engine:
        @contextmanager
        def connect(self):
            yield Connection()

    class AvailableRedis:
        def ping(self):
            return True

    class QueueWorker:
        def queue_names(self):
            return ["signal-ledger"]

    class Worker:
        @staticmethod
        def all(connection):
            return [QueueWorker()]

    monkeypatch.setattr(main_module, "engine", Engine())
    monkeypatch.setattr(main_module, "redis", AvailableRedis())
    monkeypatch.setattr(main_module, "Worker", Worker)

    response = main_module.health()
    assert response.status_code == 200
    assert json.loads(response.body)["components"] == {"database": True, "redis": True, "worker": True}
