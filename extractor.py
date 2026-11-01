import io
import re
import csv
import pdfplumber
import openpyxl
from typing import List, Dict, Tuple, Any

DELIMITERS = [",", "\t", ";", "|"]

_NUMERIC_RE = re.compile(r"^-?\d[\d,]*\.?\d*$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$|^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$")


def _lines_to_rows(text: str) -> List[Dict[str, Any]]:
    return [{"raw_text": line} for line in text.splitlines() if line.strip()]


def _split(line: str, delimiter: str) -> List[str]:
    return [field.strip() for field in line.split(delimiter)]


def _looks_like_value(field: str) -> bool:
    """True when a field looks like an amount or a date rather than a heading."""
    raw = field.strip()
    if not raw:
        return False
    if _DATE_RE.match(raw):
        return True
    return bool(_NUMERIC_RE.match(raw.replace("$", "").replace(",", "")))


def _rows_from_group(group: List[str], delimiter: str) -> List[Dict[str, Any]]:
    """Treat the first all-text line in group as the header and parse the rest."""
    header_index = None
    for index, line in enumerate(group):
        fields = _split(line, delimiter)
        if not any(_looks_like_value(field) for field in fields):
            header_index = index
            break
    if header_index is None:
        return []

    headers = _split(group[header_index], delimiter)
    rows = []
    for line in group[header_index + 1:]:
        fields = _split(line, delimiter)
        row = {}
        for position, header in enumerate(headers):
            row[header] = fields[position] if position < len(fields) else None
        if any(str(value).strip() for value in row.values() if value is not None):
            rows.append(row)
    return rows


def _parse_csv_text(text: str) -> List[Dict[str, Any]]:
    sample = text.strip()
    if not sample:
        return []

    lines = [line for line in sample.splitlines() if line.strip()]
    if not lines:
        return []
    if len(lines) == 1:
        if "|" in lines[0] and len(_split(lines[0], "|")) > 1:
            rows = _rows_from_group(lines, "|")
            if rows:
                return rows
        return [{"raw_text": lines[0]}]

    # The delimiter is the one appearing on the most lines, not the one on line 1.
    best_delimiter, best_count = None, 0
    for delimiter in DELIMITERS:
        count = sum(1 for line in lines if delimiter in line)
        if count > best_count:
            best_delimiter, best_count = delimiter, count
    if best_delimiter is None or best_count < 2:
        return _lines_to_rows(sample)

    # Keep only lines with the most common field count: drops preamble and footer.
    by_field_count: Dict[int, List[str]] = {}
    for line in lines:
        if best_delimiter in line:
            by_field_count.setdefault(len(_split(line, best_delimiter)), []).append(line)
    modal_count = max(by_field_count, key=lambda count: len(by_field_count[count]))
    group = by_field_count[modal_count]
    if modal_count < 2 or len(group) < 2:
        return _lines_to_rows(sample)

    rows = _rows_from_group(group, best_delimiter)
    if rows:
        return rows

    try:
        reader = csv.DictReader(io.StringIO(sample), delimiter=best_delimiter)
        legacy = []
        for row in reader:
            if any(str(v).strip() for v in row.values() if v is not None):
                legacy.append(row)
        if legacy:
            return legacy
    except Exception:
        pass
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
