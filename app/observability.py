"""Small, dependency-free operational logging helpers.

Events deliberately contain only route/method/status identifiers and bounded
operational counts. Capture contents, raw addresses, credentials, secrets, and
storage paths must never enter application logs.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


SENSITIVE_FIELD_PARTS = ("address", "secret", "password", "token", "cookie", "authorization", "raw_path", "upload")


def safe_fields(fields: dict[str, Any]) -> dict[str, Any]:
    """Drop fields whose names could carry sensitive operator or capture data."""
    return {
        key: value
        for key, value in fields.items()
        if not any(part in key.lower() for part in SENSITIVE_FIELD_PARTS)
    }


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "event": record.getMessage(),
            "logger": record.name,
        }
        payload.update(safe_fields(getattr(record, "fields", {})))
        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging() -> None:
    logger = logging.getLogger("signal_ledger")
    if logger.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def event(logger: logging.Logger, name: str, **fields: Any) -> None:
    logger.info(name, extra={"fields": safe_fields(fields)})
