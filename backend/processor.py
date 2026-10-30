from typing import List, Dict, Any
import io
import extractor
import matcher

def extract_text(file_bytes: bytes) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            text = ""
            for p in pdf.pages:
                text = text + (p.extract_text() or "") + "\n"
            if text.strip():
                return text
    except Exception:
        pass
    return file_bytes.decode("utf-8", errors="ignore")

def process_file(file_bytes: bytes) -> List[Dict[str, Any]]:
    rows, source_name = extractor.extract_rows(file_bytes)
    records = matcher.build_records(rows, source_name)
    return records
