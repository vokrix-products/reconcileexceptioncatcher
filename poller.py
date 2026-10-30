"""Poller for ReconcileExceptionCatcher.

Drains pending process_upload jobs from Supabase, runs extractor + matcher,
writes reconciliation rows into the records table, uploads a JSON result to the
results bucket, marks the job completed/failed and drops a notification row.
"""
import datetime
import json
import os
import time
import traceback

import requests

import processor

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
PRODUCT_ID = os.environ.get("PRODUCT_ID", "reconcileexceptioncatcher")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

REST_URL = SUPABASE_URL + "/rest/v1"
SB_HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": "Bearer " + SUPABASE_SERVICE_KEY,
}
UPLOADS_BUCKET = "uploads"
RESULTS_BUCKET = "results"
POLL_INTERVAL = 60


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def download_file(bucket, file_path):
    if file_path.startswith(bucket + "/"):
        file_path = file_path[len(bucket) + 1:]
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{file_path}"
    resp = requests.get(url, headers={"Authorization": f"Bearer {SUPABASE_SERVICE_KEY}", "apikey": SUPABASE_SERVICE_KEY})
    resp.raise_for_status()
    return resp.content


def upload_file(bucket, file_path, content, content_type="application/octet-stream"):
    url = SUPABASE_URL + "/storage/v1/object/" + bucket + "/" + file_path
    headers = {
        "Authorization": "Bearer " + SUPABASE_SERVICE_KEY,
        "apikey": SUPABASE_SERVICE_KEY,
        "Content-Type": content_type,
        "x-upsert": "true",
    }
    try:
        resp = requests.post(url, headers=headers, data=content, timeout=60)
    except Exception as exc:
        print("upload error: " + str(exc))
        return None
    if resp.status_code not in (200, 201):
        print("upload failed %s: %s" % (resp.status_code, resp.text[:300]))
        return None
    return file_path


def fetch_pending_jobs():
    url = REST_URL + "/jobs"
    params = {
        "select": "*",
        "status": "eq.pending",
        "job_type": "eq.process_upload",
        "product_id": "eq." + PRODUCT_ID,
        "limit": "5",
    }
    try:
        resp = requests.get(url, headers=SB_HEADERS, params=params, timeout=30)
    except Exception as exc:
        print("job fetch error: " + str(exc))
        return []
    if resp.status_code != 200:
        print("job fetch failed %s: %s" % (resp.status_code, resp.text[:300]))
        return []
    try:
        return resp.json() or []
    except Exception:
        return []


def mark_job_running(job_id):
    try:
        requests.patch(
            REST_URL + "/jobs",
            headers={**SB_HEADERS, "Content-Type": "application/json", "Prefer": "return=minimal"},
            params={"id": "eq." + str(job_id)},
            json={"status": "processing", "started_at": now_iso()},
            timeout=30,
        )
    except Exception as exc:
        print("mark_job_running failed for %s: %s" % (job_id, exc))


def update_job(job_id, status, output_file_path=None, result_summary=None):
    payload = {"status": status, "completed_at": now_iso()}
    if output_file_path:
        payload["output_file_path"] = output_file_path
    if result_summary is not None:
        payload["result_summary"] = result_summary
    try:
        resp = requests.patch(
            REST_URL + "/jobs",
            headers={**SB_HEADERS, "Content-Type": "application/json", "Prefer": "return=minimal"},
            params={"id": "eq." + str(job_id)},
            json=payload,
            timeout=30,
        )
        if resp.status_code not in (200, 204):
            print("update_job failed %s: %s" % (resp.status_code, resp.text[:300]))
    except Exception as exc:
        print("update_job error for %s: %s" % (job_id, exc))


def insert_records(records, job):
    customer_id = job.get("customer_id")
    for r in records:
        try:
            resp = requests.post(
                REST_URL + "/records",
                headers={**SB_HEADERS, "Content-Type": "application/json", "Prefer": "return=minimal"},
                json={
                    "product_id": PRODUCT_ID,
                    "customer_id": customer_id,
                    "title": r["title"],
                    "status": r["status"],
                    "details": r["details"],
                    "source_file_path": job["input_file_path"],
                    "due_date": r.get("due_date"),
                },
                timeout=30,
            )
            if resp.status_code not in (200, 201, 204):
                print("record insert failed %s: %s" % (resp.status_code, resp.text[:300]))
        except Exception as exc:
            print("record insert error: " + str(exc))


def notify(job, ok):
    if ok:
        title = "Processing complete"
        body = "Your upload has been processed successfully."
        ntype = "success"
    else:
        title = "Processing failed"
        body = "There was an error processing your upload."
        ntype = "error"
    try:
        requests.post(
            "https://njyvnmczoydsaewvfhyq.supabase.co/rest/v1/notifications",
            headers={**SB_HEADERS, "Content-Type": "application/json", "Prefer": "return=minimal"},
            json={
                "product_id": PRODUCT_ID,
                "customer_id": job.get("customer_id"),
                "title": title,
                "body": body,
                "type": ntype,
                "read": False,
            },
            timeout=30,
        )
    except Exception as exc:
        print("notification failed: " + str(exc))


def process_job(job):
    job_id = job.get("id")
    input_file_path = job.get("input_file_path")
    print("processing job %s file=%s" % (job_id, input_file_path))
    mark_job_running(job_id)

    if not input_file_path:
        update_job(job_id, "failed", result_summary={"error": "missing input_file_path"})
        notify(job, False)
        return

    try:
        file_bytes = download_file(UPLOADS_BUCKET, input_file_path)
        records = processor.process_file(file_bytes)
        insert_records(records, job)

        result_doc = {
            "product_id": PRODUCT_ID,
            "job_id": job_id,
            "customer_id": job.get("customer_id"),
            "source_file_path": input_file_path,
            "record_count": len(records),
            "records": records,
            "generated_at": now_iso(),
        }
        result_bytes = json.dumps(result_doc, indent=2, default=str).encode("utf-8")
        base = os.path.basename(input_file_path) or (str(job_id) + ".bin")
        output_path = "%s/%s/%s-%s.json" % (PRODUCT_ID, job.get("customer_id"), job_id, base)
        uploaded = upload_file(RESULTS_BUCKET, output_path, result_bytes, "application/json")

        summary = {
            "record_count": len(records),
            "confirmed": sum(1 for r in records if str(r.get("status", "")).startswith("confirmed")),
            "exception": sum(1 for r in records if str(r.get("status", "")).startswith("exception")),
        }
        update_job(job_id, "completed", output_file_path=uploaded or output_path, result_summary=summary)
        notify(job, True)
        print("job %s completed with %s records" % (job_id, len(records)))
    except Exception as exc:
        print("job %s failed: %s" % (job_id, exc))
        traceback.print_exc()
        update_job(job_id, "failed", result_summary={"error": str(exc)[:500]})
        notify(job, False)


def poll():
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("SUPABASE_URL / SUPABASE_SERVICE_KEY not set - poller cannot start")
        return
    print("poller running for product " + PRODUCT_ID)
    while True:
        try:
            for job in fetch_pending_jobs():
                process_job(job)
        except Exception as exc:
            print("poll loop error: " + str(exc))
        time.sleep(60)


if __name__ == "__main__":
    print("Poller started")
    poll()
