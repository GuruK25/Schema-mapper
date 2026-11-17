# Schema Mapper

Maps non-standard supplier files (CSV, XLSX, PDF) to canonical PO line item fields.

## Problem

Every supplier sends packing slips and ASNs in a different format and terminology.
This component reads those files and reliably maps each column to the correct target field,
then links each row to the matching PO line item.

## Architecture

```
File upload
    ↓
[Fingerprint]   Detect Excel-opened file corruption (BOM, scientific notation, etc.)
    ↓
[Ingest]        Read CSV / XLSX / PDF as raw strings — no type inference
    ↓
[Sanitize]      Fix leading zeros, scientific notation barcodes, comma-thousands, date coercion
    ↓
[Map columns]   Hybrid scorer: linguistic name match + instance-based domain classifier
    ↓
[Link rows]     Match supplier rows → PO line items via SKU xref + fuzzy description
    ↓
[Review queue]  Surface low-confidence and unrecoverable items for human review
```

## Stack

- **Python 3.11+**
- **FastAPI** — REST API
- **openpyxl** — raw XLSX reading (no Excel rendering)
- **pdfplumber** — PDF table extraction
- **rapidfuzz** — fuzzy string matching
- **pydantic v2** — typed output models

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn api.main:app --reload
```

API docs: http://localhost:8000/docs

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/map` | Upload a supplier file, get a `MappingResult` |
| `GET`  | `/suppliers/{id}/profile` | Fetch saved mapping profile for a supplier |
| `POST` | `/suppliers/{id}/profile` | Save a confirmed mapping profile |
| `GET`  | `/review` | List items pending human review |
| `GET`  | `/health` | Health check |

## Output shape

See `mapper/models.py` for the full `MappingResult` schema.
