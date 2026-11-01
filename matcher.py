import hashlib
import json
import re
import datetime
from typing import Any, Dict, List, Optional
import config

def _normalize_key(key: Any) -> str:
    """Collapse a column heading to a comparable token: 'Amount (USD)' -> 'amount'."""
    text = re.sub(r"\([^)]*\)", " ", str(key))
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return text

def _find_value(row: Dict[str, Any], candidates: List[str]) -> Optional[Any]:
    lookup = {}
    for key, value in row.items():
        lookup.setdefault(_normalize_key(key), value)
    for c in candidates:
        value = lookup.get(_normalize_key(c))
        if value is not None and str(value).strip() != "":
            return value
    return None

def _parse_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip().replace(",", "").replace("$", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None

def _parse_date(value: Any) -> Optional[datetime.date]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    formats = [
        "%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y", "%d/%m/%y",
        "%Y/%m/%d", "%d-%b-%Y", "%d-%b-%y", "%b %d, %Y", "%B %d, %Y",
        "%Y-%m-%d %H:%M:%S"
    ]
    for fmt in formats:
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.date.fromisoformat(s)
    except ValueError:
        pass
    return None

def _to_iso_date(dt: Optional[datetime.date]) -> Optional[str]:
    return dt.isoformat() if dt else None

def build_records(rows: List[Dict[str, Any]], source_name: str) -> List[Dict[str, Any]]:
    records = []
    for idx, raw_row in enumerate(rows, start=1):
        # Title
        title = _find_value(raw_row, config.TITLE_COLUMN_CANDIDATES)
        if title is None:
            for v in raw_row.values():
                if v is not None and str(v).strip():
                    title = str(v).strip()
                    break
        if title is None:
            title = "Unnamed Record"

        # Amount
        amount_val = _find_value(raw_row, config.AMOUNT_COLUMN_CANDIDATES)
        amount = _parse_float(amount_val)

        # Date
        date_val = _find_value(raw_row, config.DATE_COLUMN_CANDIDATES)
        parsed_date = _parse_date(date_val)
        due_date = _to_iso_date(parsed_date)

        # Status
        if amount is not None and parsed_date is not None:
            status = config.STATUS_CONFIRMED
        else:
            status = config.STATUS_EXCEPTION

        # Details
        details = dict(raw_row)
        details["source_file_name"] = f"uploaded_{source_name}"
        details["source_row_number"] = idx
        details["row_uid"] = hashlib.sha256(
            f"{source_name}:{idx}:{json.dumps(raw_row, sort_keys=True, default=str)}".encode("utf-8")
        ).hexdigest()
        details["extracted_amount"] = amount
        details["extracted_date"] = due_date

        record = {
            "title": str(title),
            "status": status,
            "details": details,
            "due_date": due_date,
        }
        records.append(record)
    return records
