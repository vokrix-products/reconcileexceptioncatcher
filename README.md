# ReconcileExceptionCatcher

Backend processing module for the file-first reconciliation workbench.

**Archetype:** File ingestion / reconciliation exception catcher. It accepts raw uploaded files (PDF, Excel, CSV, or plain text), extracts tabular rows, normalizes each row into a structured record, assigns a reconciliation status, and flags anything that could not be fully parsed as an exception.

## What the poller expects as input

The poller/worker calls the single public entry point:

```python
from processor import process_file

records = process_file(file_bytes)  # file_bytes: raw bytes of the uploaded file
```

- Input: raw file bytes (any format the extractor supports: PDF, XLSX, CSV, plain UTF-8 text, or empty).
- Output: a `list[dict]`. Each record has the shape:

```json
{
  "title": "Acme",
  "status": "confirmed:good",
  "due_date": "2024-01-15",
  "details": {
    "source_file_name": "uploaded_csv",
    "source_row_number": 1,
    "row_uid": "<sha256 hex>",
    "extracted_amount": 9.99,
    "extracted_date": "2024-01-15"
  }
}
```

- `status` is always exactly one of `confirmed:good` or `exception:warning`.
  - `confirmed:good`: both an amount and a date were successfully parsed.
  - `exception:warning`: amount and/or date could not be parsed (row surfaced as an exception).
- `due_date` is a top-level ISO date string (`YYYY-MM-DD`) or `null`.
- `details` carries the original row plus extraction metadata and a stable `row_uid`.
- Empty input returns an empty list (`[]`), never `null`.

## Files

- `processor.py`: main entry point, `process_file(file_bytes) -> list[dict]`.
- `extractor.py`: format detection and extraction (PDF via pdfplumber, Excel via openpyxl, then UTF-8 text/CSV fallback).
- `matcher.py`: normalizes rows into records — title detection, amount/date parsing, status assignment, details + `row_uid` build, top-level `due_date`.
- `config.py`: constants, including the exact status strings and the column candidate lists for title, amount, and date.
- `run_demo.py`: zero-arg demo with hardcoded CSV bytes.
- `run_tests.py`: zero-arg tests for CSV, text fallback, empty bytes, and Excel bytes.

## Running

```
pip install -r requirements.txt
python3 run_demo.py
python3 run_tests.py
```

Both scripts are zero-argument and exit 0 on success.
Railway: reconcileexceptioncatcher
Cloudflare: reconcileexceptioncatcher.vokrix.co


Landing: https://vokrix.co/reconcileexceptioncatcher

Outreach: active

## Dashboard (Vercel)

- `dashboard/`: Vite + React + TanStack Router dashboard.
- `dashboard/vercel.json`: SPA rewrite of all routes to `/index.html`.
- Product copy is driven by Vercel env vars (`VITE_PRODUCT_ARCHETYPE`, `VITE_RECORDS_LABEL`, `VITE_RECORDS_SUBTITLE`, `VITE_FILTER_PLACEHOLDER`, `VITE_UPLOAD_DESCRIPTION`, `VITE_UPLOAD_EMPTY_STATE`).
- Records are surfaced as reconciliation rows with statuses `confirmed:good` and `exception:warning`.

## Worker (Railway)

- Container entrypoint: `python3 poller.py` (see `Dockerfile` at repo root).
- `poll()` runs a `while True` loop with a 60 second sleep and claims jobs where `status=eq.pending`, `job_type=eq.process_upload`, `product_id=eq.$PRODUCT_ID`.
- Environment: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `PRODUCT_ID`, `ANTHROPIC_API_KEY`.
- Each job: download the upload from the `uploads` bucket, run `processor.process_file(file_bytes)`, insert one row per result into `records` (with `source_file_path` from `job.input_file_path`), upload the result JSON to the `results` bucket, then set the job to `completed` or `failed` with `output_file_path`, `result_summary`, and `completed_at`.
- A notification row is written to `notifications` on both success and failure; notification errors never break the poll loop.

## Domain

- Cloudflare: `reconcileexceptioncatcher.vokrix.co` points at the Vercel dashboard deployment.
- Landing page: https://vokrix.co/reconcileexceptioncatcher
