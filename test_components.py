"""
Verify all components work without requiring a display or OCR engines installed.
Tests: imports, data manager, templates, export (CSV/JSON/Excel), smart_parse.
"""
import os
import sys
import tempfile
import json

def test_imports():
    print("[TEST] Importing modules...")
    from data_manager import DataManager
    from ocr_engine import smart_parse_lines
    from pdf_handler import get_pdf_page_count
    print("  OK: All modules import successfully")

def test_data_manager():
    print("[TEST] DataManager...")
    from data_manager import DataManager
    dm = DataManager()

    dm.update_field("Name", "John Doe")
    dm.update_field("Amount", "$150.00")
    dm.update_field("Date", "2024-01-15")
    assert dm.save_current_entry()
    assert dm.get_entry_count() == 1

    dm.update_field("Name", "Jane Smith")
    dm.update_field("Amount", "$275.50")
    dm.update_field("Date", "2024-02-20")
    assert dm.save_current_entry()
    assert dm.get_entry_count() == 2

    assert not dm.save_current_entry()  # empty should fail
    print(f"  OK: {dm.get_entry_count()} entries saved")

    return dm

def test_templates():
    print("[TEST] Templates...")
    from data_manager import DataManager
    dm = DataManager()

    names = dm.get_template_names()
    assert "Invoice" in names
    assert "Receipt" in names
    assert "Form" in names
    assert "Medical" in names

    invoice_fields = dm.get_template_fields("Invoice")
    assert "Invoice No" in invoice_fields
    assert "Total" in invoice_fields

    dm.save_template("MyCustom", ["Field A", "Field B", "Field C"])
    assert "MyCustom" in dm.get_template_names()
    assert dm.get_template_fields("MyCustom") == ["Field A", "Field B", "Field C"]
    print(f"  OK: {len(dm.get_template_names())} templates available")

def test_export_csv(dm):
    print("[TEST] CSV export...")
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
        path = f.name
    assert dm.export_csv(path)
    with open(path, "r") as f:
        content = f.read()
    assert "John Doe" in content
    assert "Jane Smith" in content
    assert "$150.00" in content
    os.unlink(path)
    print(f"  OK: CSV exported with correct data")

def test_export_json(dm):
    print("[TEST] JSON export...")
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        path = f.name
    assert dm.export_json(path)
    with open(path, "r") as f:
        data = json.load(f)
    assert len(data) == 2
    assert data[0]["Name"] == "John Doe"
    assert data[1]["Amount"] == "$275.50"
    os.unlink(path)
    print(f"  OK: JSON exported with {len(data)} entries")

def test_export_excel(dm):
    print("[TEST] Excel export...")
    try:
        import openpyxl
    except ImportError:
        print("  SKIP: openpyxl not installed")
        return

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    assert dm.export_excel(path)
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    assert ws.title == "TODE Data"
    rows = list(ws.iter_rows(values_only=True))
    assert len(rows) == 3  # header + 2 entries
    assert "Name" in rows[0]
    wb.close()
    os.unlink(path)
    print(f"  OK: Excel exported with styled headers + {len(rows)-1} rows")

def test_smart_parse():
    print("[TEST] Smart parse lines...")
    from ocr_engine import smart_parse_lines

    text = """Name: John Doe
Date: 2024-01-15
Amount: $150.00
Ref: INV-001"""

    parsed = smart_parse_lines(text)
    assert parsed["Name"] == "John Doe"
    assert parsed["Date"] == "2024-01-15"
    assert parsed["Amount"] == "$150.00"
    assert parsed["Ref"] == "INV-001"
    print(f"  OK: Parsed {len(parsed)} key-value pairs")

    text2 = "Total = 500\nTax = 50"
    parsed2 = smart_parse_lines(text2)
    assert parsed2["Total"] == "500"
    assert parsed2["Tax"] == "50"
    print(f"  OK: Parsed '=' separated values too")

def test_delete_edit_entries():
    print("[TEST] Entry delete/edit...")
    from data_manager import DataManager
    dm = DataManager()

    dm.update_field("A", "1")
    dm.save_current_entry()
    dm.update_field("A", "2")
    dm.save_current_entry()
    dm.update_field("A", "3")
    dm.save_current_entry()

    assert dm.get_entry_count() == 3
    assert dm.edit_entry(1, "A", "EDITED")
    assert dm.entries[1]["A"] == "EDITED"

    assert dm.delete_entry(2)
    assert dm.get_entry_count() == 2
    print("  OK: Edit and delete work correctly")

def test_tkinter_loads():
    print("[TEST] Tkinter import...")
    try:
        import tkinter as tk
        print("  OK: tkinter available")
    except ImportError:
        print("  SKIP: tkinter not available (headless environment)")

def main():
    print("=" * 50)
    print("TODE Entry v1 — Component Tests")
    print("=" * 50)

    test_imports()
    test_tkinter_loads()
    dm = test_data_manager()
    test_templates()
    test_smart_parse()
    test_delete_edit_entries()
    test_export_csv(dm)
    test_export_json(dm)
    test_export_excel(dm)

    print("=" * 50)
    print("ALL TESTS PASSED")
    print("=" * 50)

if __name__ == "__main__":
    main()
