"""Format-agnostic file reader. All columns returned as raw strings."""
from pathlib import Path


SUPPORTED = {".csv", ".xlsx", ".xls", ".pdf"}


def read_file(path: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    """
    Returns (headers, rows) where every value is a raw string.
    Raises ValueError for unsupported formats.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError(f"Unsupported file format: {suffix}")

    if suffix == ".csv":
        return _read_csv(path)
    if suffix in (".xlsx", ".xls"):
        return _read_xlsx(path)
    if suffix == ".pdf":
        return _read_pdf(path)


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    import chardet, csv

    raw = path.read_bytes()
    encoding = chardet.detect(raw)["encoding"] or "utf-8"
    text = raw.decode(encoding, errors="replace").lstrip("﻿")  # strip BOM

    reader = csv.DictReader(text.splitlines())
    headers = list(reader.fieldnames or [])
    rows = [{k: str(v or "") for k, v in row.items()} for row in reader]
    return headers, rows


def _read_xlsx(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=False)

    header_row = next(rows_iter, None)
    if header_row is None:
        return [], []

    headers = [str(cell.value or f"col_{i}") for i, cell in enumerate(header_row)]
    rows = []
    for row in rows_iter:
        record = {}
        for header, cell in zip(headers, row):
            record[header] = _cell_to_str(cell)
        rows.append(record)

    wb.close()
    return headers, rows


def _cell_to_str(cell) -> str:
    """Convert an openpyxl cell to string without Excel's rendering."""
    import openpyxl.utils.datetime as xl_dt
    from datetime import datetime

    val = cell.value
    if val is None:
        return ""
    if isinstance(val, datetime):
        return val.date().isoformat()
    return str(val)


def _read_pdf(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                headers = [str(h or f"col_{i}") for i, h in enumerate(table[0])]
                rows = [
                    {headers[i]: str(v or "") for i, v in enumerate(row)}
                    for row in table[1:]
                ]
                return headers, rows
    return [], []
