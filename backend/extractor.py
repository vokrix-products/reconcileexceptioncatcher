import io
import csv
import pdfplumber
import openpyxl
from typing import List, Dict, Tuple, Any

def _lines_to_rows(text: str) -> List[Dict[str, Any]]:
    return [{"raw_text": line} for line in text.splitlines() if line.strip()]

def _looks_delimited(sample: str) -> bool:
    first = sample.splitlines()[0] if sample.splitlines() else ""
    return any(delim in first for delim in [",", "\t", ";", "|"])

def _parse_csv_text(text: str) -> List[Dict[str, Any]]:
    sample = text.strip()
    if not sample:
        return []
    if "\n" not in sample:
        return [{"raw_text": sample}]
    if not _looks_delimited(sample):
        return _lines_to_rows(sample)
    try:
        reader = csv.DictReader(io.StringIO(sample))
        rows = []
        for row in reader:
            if any(str(v).strip() for v in row.values() if v is not None):
                rows.append(row)
        if rows:
            return rows
        return _lines_to_rows(sample)
    except Exception:
        return _lines_to_rows(sample)

def extract_rows(file_bytes: bytes) -> Tuple[List[Dict[str, Any]], str]:
    # Try PDF first
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        if text.strip():
            rows = _parse_csv_text(text)
            if rows:
                return rows, "pdf"
            lines = [line for line in text.splitlines() if line.strip()]
            if lines:
                return [{"raw_text": line} for line in lines], "pdf"
    except Exception:
        pass

    # Try Excel
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
        ws = wb.active
        rows = []
        headers = None
        for row in ws.iter_rows(values_only=True):
            if headers is None:
                headers = [str(cell) if cell is not None else f"col_{i}" for i, cell in enumerate(row)]
                continue
            if any(v is not None and str(v).strip() != "" for v in row):
                row_dict = {}
                for i, header in enumerate(headers):
                    value = row[i] if i < len(row) else None
                    row_dict[header] = value
                rows.append(row_dict)
        wb.close()
        if rows:
            return rows, "excel"
    except Exception:
        pass

    # Fallback: decode UTF-8 text/CSV
    text = file_bytes.decode("utf-8", errors="ignore")
    rows = _parse_csv_text(text)
    if rows:
        return rows, "csv"
    lines = [line for line in text.splitlines() if line.strip()]
    if lines:
        return [{"raw_text": line} for line in lines], "text"
    return [], "empty"
