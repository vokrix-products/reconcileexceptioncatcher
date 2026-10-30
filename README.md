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
