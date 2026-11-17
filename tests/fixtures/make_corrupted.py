"""
Generates test fixture files that simulate Excel-opened corruption.
Run once: python tests/fixtures/make_corrupted.py
"""
from pathlib import Path

HERE = Path(__file__).parent


def make_excel_corrupted_csv():
    """
    Simulates a CSV that was opened and re-saved by Excel:
    - UTF-8 BOM at the start
    - Windows CRLF line endings
    - Barcode in scientific notation (5901234123457 → 5.90123E+12)
    - SKU with leading zeros stripped (00456 → 456)
    - Quantity with thousands comma (1200 → "1,200")
    - SKU that looks like it was coerced to a date serial (item "1-2" → 45293)
    """
    lines = [
        "Part Number,Description,Order Qty,Ship Qty,Unit Price,Barcode,Ship Date",
        '456,Widget A Premium,"1,200",100,12.50,5.90123E+12,2024-11-15',
        "OUR-789,Widget B Standard,50,50,8.75,9780306406157,2024-11-15",
        "45293,Date-Coerced SKU,30,30,3.20,9780140328721,2024-11-15",
        "OUR-321,Connector Type-C,200,150,22.00,4006381333931,2024-11-15",
    ]
    # BOM + CRLF line endings — exactly what Excel produces
    content = "﻿" + "\r\n".join(lines) + "\r\n"
    path = HERE / "excel_corrupted.csv"
    path.write_bytes(content.encode("utf-8"))
    print(f"Created: {path}")


def make_no_headers_csv():
    """
    A CSV with no column headers at all — tests instance-based domain classification.
    """
    lines = [
        "OUR-456,Widget A Premium,100,100,12.50,1250.00,2024-11-15",
        "OUR-789,Widget B Standard,50,50,8.75,437.50,2024-11-15",
        "OUR-321,Connector Type-C,200,150,3.20,480.00,2024-11-15",
    ]
    path = HERE / "no_headers.csv"
    path.write_text("\n".join(lines))
    print(f"Created: {path}")


if __name__ == "__main__":
    make_excel_corrupted_csv()
    make_no_headers_csv()
    print("All fixtures generated.")
