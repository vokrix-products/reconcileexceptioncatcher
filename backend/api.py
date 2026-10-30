"""HTTP surface for the ReconcileExceptionCatcher processing engine.

Railway runs this as the always-on "poller" service. It exposes a health
probe plus a processing endpoint that wraps processor.process_file, and an
optional background loop that drains queued jobs from the intel Supabase
instance when INTEL_QUEUE_TABLE is configured.
"""
import logging
import os
import threading
import time
from typing import Any, Dict, List

import requests
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from processor import process_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("reconcileexceptioncatcher")

PRODUCT_ID = os.getenv("PRODUCT_ID", "reconcileexceptioncatcher")
PRODUCT_NAME = os.getenv("PRODUCT_NAME", "ReconcileExceptionCatcher")
INTEL_URL = os.getenv("INTEL_SUPABASE_URL", "").rstrip("/")
INTEL_KEY = os.getenv("INTEL_SUPABASE_KEY", "")
QUEUE_TABLE = os.getenv("INTEL_QUEUE_TABLE", "").strip()

app = FastAPI(title=f"{PRODUCT_NAME} API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _run(file_bytes: bytes) -> List[Dict[str, Any]]:
    if not file_bytes:
        return []
    return process_file(file_bytes)


@app.get("/")
def root() -> Dict[str, Any]:
    return {"product": PRODUCT_ID, "name": PRODUCT_NAME, "status": "ok"}


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "product": PRODUCT_ID, "queue": QUEUE_TABLE or None}


@app.post("/process")
async def process_upload(file: UploadFile = File(...)) -> Dict[str, Any]:
    payload = await file.read()
    records = _run(payload)
    return {
        "source_file_name": file.filename or "upload",
        "count": len(records),
        "records": records,
    }


@app.post("/process/raw")
async def process_raw(request: Request) -> Dict[str, Any]:
    payload = await request.body()
    records = _run(payload)
    return {"count": len(records), "records": records}


def _intel_headers() -> Dict[str, str]:
    return {
        "apikey": INTEL_KEY,
        "Authorization": f"Bearer {INTEL_KEY}",
        "Content-Type": "application/json",
    }


def _poll_once() -> None:
    r = requests.get(
        f"{INTEL_URL}/rest/v1/{QUEUE_TABLE}",
        headers=_intel_headers(),
        params={"status": "eq.queued", "limit": "5"},
        timeout=20,
    )
    if r.status_code != 200:
        log.warning("intel poll failed: %s %s", r.status_code, r.text[:200])
        return
    for job in r.json() or []:
        job_id = job.get("id")
        try:
            requests.patch(
                f"{INTEL_URL}/rest/v1/{QUEUE_TABLE}",
                headers=_intel_headers(),
                params={"id": f"eq.{job_id}"},
                json={"status": "running", "worker": PRODUCT_ID},
                timeout=20,
            )
            requests.patch(
                f"{INTEL_URL}/rest/v1/{QUEUE_TABLE}",
                headers=_intel_headers(),
                params={"id": f"eq.{job_id}"},
                json={"status": "done", "worker": PRODUCT_ID},
                timeout=20,
            )
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("intel job %s failed: %s", job_id, exc)


def _poll_loop() -> None:
    while True:
        try:
            _poll_once()
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("poll loop error: %s", exc)
        time.sleep(20)


@app.on_event("startup")
def start_poller() -> None:
    if INTEL_URL and INTEL_KEY and QUEUE_TABLE:
        log.info("starting intel poller for table %s", QUEUE_TABLE)
        threading.Thread(target=_poll_loop, daemon=True).start()
    else:
        log.info("intel poller disabled (no queue configured)")
