import io
import openpyxl
from processor import process_file

def test_csv():
    data = b"supplier,product,price\nAcme,Widget,9.99\n"
    results = process_file(data)
    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]["title"] == "Acme"
    assert results[0]["status"] in ["confirmed:good", "exception:warning"]
    assert "details" in results[0]
    assert "due_date" in results[0]
    print("test_csv passed")

def test_csv_pipe():
    data = b"supplier|description|amount|date\nAcme|Widget|9.99|2024-01-15\n"
    results = process_file(data)
    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]["title"] == "Acme"
    assert results[0]["status"] == "confirmed:good"
    assert results[0]["due_date"] == "2024-01-15"
    print("test_csv_pipe passed")

def test_csv_semicolon():
    data = b"supplier;amount;date\nBeta;12.50;2024-01-16\n"
    results = process_file(data)
    assert len(results) == 1
    assert results[0]["title"] == "Beta"
    assert results[0]["status"] == "confirmed:good"
    print("test_csv_semicolon passed")

def test_csv_pipe_with_preamble():
    """Real-world ledger export: title/preamble lines above the header, a
    comma-separated footer below the data, and parenthetical column names.

    Regression for the bug where the delimiter was taken from line 1 only
    (so a preamble meant no delimiter was found), which sent every row down
    the raw_text fallback and produced all-exception output.
    """
    data = (
        "GL Reconciliation Ledger - October 2024\n"
        "Prepared by: Marcus Chen, Senior Accountant | Reviewed: Priya Raman, Controller\n"
        "Entity: Northwind Logistics Inc. | Account: 1010-0042 Operating Cash - First Meridian Bank\n"
        "Address: 4400 Harborview Blvd, Suite 300, Oakland, CA 94607\n"
        "Row | Description | Reference | Amount (USD) | Date | Status\n"
        "1 | ACH Deposit - Cascade Freight Partners | INV-2024-0871 | 18450.00 | 2024-10-02 | Matched\n"
        "2 | Wire Out - Pacific Rim Container Co. | PO-4471 | -32780.55 | 2024-10-03 | Matched\n"
        "Opening Balance (2024-10-01): 1,204,880.32\n"
        "Unreconciled Difference: 12,340.00\n"
    ).encode()
    results = process_file(data)
    assert len(results) == 2, "expected 2 data rows, got %d" % len(results)
    assert results[0]["status"] == "confirmed:good", results[0]["status"]
    assert results[1]["status"] == "confirmed:good", results[1]["status"]
    assert results[0]["title"] == "ACH Deposit - Cascade Freight Partners", results[0]["title"]
    assert results[0]["due_date"] == "2024-10-02", results[0]["due_date"]
    assert results[1]["due_date"] == "2024-10-03", results[1]["due_date"]
    print("test_csv_pipe_with_preamble passed")

def test_text_fallback():
    data = b"Hello world\nSecond line\n"
    results = process_file(data)
    assert isinstance(results, list)
    assert len(results) == 2
    print("test_text_fallback passed")

def test_empty_bytes():
    results = process_file(b"")
    assert isinstance(results, list)
    assert len(results) == 0
    print("test_empty_bytes passed")

def test_excel_bytes():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["supplier", "price", "date"])
    ws.append(["Acme", 9.99, "2024-01-15"])
    ws.append(["Beta", 12.50, "2024-01-16"])
    bio = io.BytesIO()
    wb.save(bio)
    data = bio.getvalue()
    results = process_file(data)
    assert isinstance(results, list)
    assert len(results) == 2
    assert results[0]["title"] == "Acme"
    print("test_excel_bytes passed")

if __name__ == "__main__":
    test_csv()
    test_csv_pipe()
    test_csv_semicolon()
    test_csv_pipe_with_preamble()
    test_text_fallback()
    test_empty_bytes()
    test_excel_bytes()
    print("All tests passed.")
