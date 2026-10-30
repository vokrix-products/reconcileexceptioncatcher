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
    test_text_fallback()
    test_empty_bytes()
    test_excel_bytes()
    print("All tests passed.")
