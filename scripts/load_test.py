#!/usr/bin/env python3
"""Exercise a realistic synthetic import and the primary explorer queries.

Run this only against a disposable Compose project:
  docker compose -p signal-ledger-load up -d db redis
  docker compose -p signal-ledger-load run --rm -e SIGNAL_LEDGER_LOAD_TEST=YES \
    -v "$PWD/scripts:/scripts:ro" app python /scripts/load_test.py --rows 5000
"""

import argparse
import asyncio
import json
import os
import time
from io import BytesIO

from starlette.datastructures import UploadFile

import app.main as main
import app.tasks as tasks
from app.database import SessionLocal
from app.main import devices, map_clusters, quick_import
from app.migrations import upgrade
from app.security import Principal


def fixture(rows: int) -> bytes:
    lines = ["MAC,FirstTime,SSID,CurrentLatitude,CurrentLongitude,RSSI"]
    for index in range(rows):
        address = f"00:11:22:{index >> 16:02X}:{(index >> 8) & 255:02X}:{index & 255:02X}"
        lines.append(f"{address},2026-09-10T12:{index % 60:02d}:00Z,load-check-{index % 32},45.{500 + index % 100:03d},-122.{600 + index % 100:03d},{-30 - index % 45}")
    return ("\n".join(lines) + "\n").encode()


def main_run(rows: int) -> None:
    if os.getenv("SIGNAL_LEDGER_LOAD_TEST") != "YES":
        raise SystemExit("Refusing to load data without SIGNAL_LEDGER_LOAD_TEST=YES. Use a disposable Compose project.")
    upgrade()
    original_enqueue = main.queue.enqueue
    main.queue.enqueue = lambda *args, **kwargs: None
    db = SessionLocal()
    principal = Principal(0, "load-drill", "admin")
    try:
        started = time.perf_counter()
        upload = UploadFile(filename="synthetic-load-check.csv", file=BytesIO(fixture(rows)))
        queued = asyncio.run(quick_import(source_format="wigle", file=upload, session_name="Synthetic load drill", collection_name="Disposable load drill", db=db, principal=principal))
        tasks.process_ingestion(queued["id"])
        ingest_seconds = time.perf_counter() - started

        started = time.perf_counter()
        inventory = devices(limit=100, offset=0, db=db, principal=principal)
        clusters = map_clusters(run_id=queued["capture_session_id"], limit=1000, db=db, principal=principal)
        explorer_seconds = time.perf_counter() - started
        if inventory["total"] != rows or not clusters:
            raise RuntimeError("Load drill did not return the complete imported inventory and map results")
        print(json.dumps({"rows": rows, "ingest_seconds": round(ingest_seconds, 3), "explorer_seconds": round(explorer_seconds, 3), "inventory_total": inventory["total"], "cluster_count": len(clusters)}, separators=(",", ":")))
    finally:
        main.queue.enqueue = original_enqueue
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=5000, choices=range(100, 50001))
    main_run(parser.parse_args().rows)
