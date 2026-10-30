from typing import List, Dict, Any
import extractor
import matcher

def process_file(file_bytes: bytes) -> List[Dict[str, Any]]:
    rows, source_name = extractor.extract_rows(file_bytes)
    records = matcher.build_records(rows, source_name)
    return records
