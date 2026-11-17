# Schema Mapper

A Python library and REST API that reads supplier files in **any format or structure** and maps the data to canonical Purchase Order line item fields — automatically.

Every supplier sends packing slips, ASNs, and invoices differently. Some use `Qty`, others `Units Shipped`, others `Menge`. Some send CSVs, some Excel, some PDFs. This component figures out which column is which, links each row to the right PO line, and flags anything it can't be sure about for human review.

---

## What It Does

```
Supplier file (CSV / XLSX / PDF)
         ↓
 ┌───────────────────────────────────┐
 │ 1. Fingerprint                    │  Detect Excel-opened corruption before anything else
 │ 2. Ingest                         │  Read all values as raw strings — no type guessing
 │ 3. Sanitize                       │  Fix leading zeros, scientific notation, comma-thousands
 │ 4. Map columns                    │  Match supplier headers → target fields (hybrid AI)
 │ 5. Link rows                      │  Match each row to the correct PO line item
 │ 6. Score + review queue           │  Flag low-confidence items for human sign-off
 └───────────────────────────────────┘
         ↓
 MappingResult (JSON)
```

**Example:** a supplier sends a file with columns `Art. Nr.`, `Menge`, `Stk-Preis`, `Gesamt`.
Schema Mapper maps them to `supplier_sku`, `qty_shipped`, `unit_price`, `total_price` automatically — even with no prior configuration for that supplier.

---

## Project Structure

```
Schema-mapper/
├── mapper/                     # Core library (use this directly or via the API)
│   ├── models.py               # All Pydantic output types (MappingResult, MappedRow, etc.)
│   ├── pipeline.py             # Main entry point — orchestrates all stages
│   ├── ingestion/
│   │   └── reader.py           # Format-agnostic file reader (CSV, XLSX, PDF)
│   ├── sanitize/
│   │   ├── fingerprint.py      # Excel corruption detector
│   │   └── sanitizers.py       # Per-field value fixers
│   ├── matching/
│   │   ├── domain_classifier.py    # Classifies columns by their data values
│   │   ├── linguistic_matcher.py   # Fuzzy synonym matching on column headers
│   │   └── hybrid_scorer.py        # Combines both into a ranked confidence score
│   ├── linkage/
│   │   └── record_linker.py    # Matches supplier rows → PO line items
│   └── profiles/
│       └── profile_store.py    # Save/load confirmed per-supplier mappings
├── api/                        # FastAPI REST service
│   ├── main.py                 # App entry point
│   └── routes/
│       ├── upload.py           # POST /map
│       ├── profiles.py         # GET/POST /suppliers/{id}/profile
│       └── review.py           # GET /review
├── tests/                      # Test suite
├── requirements.txt
└── README.md
```

---

## Requirements

- Python 3.11 or higher
- pip

---

## Clone & Install

```bash
# 1. Clone the repository
git clone https://github.com/GuruK25/Schema-mapper.git
cd Schema-mapper

# 2. Create a virtual environment
python -m venv .venv

# 3. Activate it
#    On Linux / macOS:
source .venv/bin/activate
#    On Windows:
.venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt
```

---

## Run the API

```bash
uvicorn api.main:app --reload
```

The API is now running at **http://localhost:8000**

Interactive docs (Swagger UI): **http://localhost:8000/docs**

---

## API Usage

### Map a supplier file

Upload any supplier file and get back a full `MappingResult` JSON object.

```bash
curl -X POST http://localhost:8000/map \
  -F "file=@supplier_packing_slip.csv" \
  -F "supplier_id=ACME_CORP" \
  -F "po_number=PO-20241117-001"
```

**With an XLSX file:**
```bash
curl -X POST http://localhost:8000/map \
  -F "file=@delivery_note.xlsx" \
  -F "supplier_id=SUPPLIER_42"
```

**Response shape:**
```json
{
  "metadata": {
    "file_name": "supplier_packing_slip.csv",
    "supplier_id": "ACME_CORP",
    "po_number": "PO-20241117-001",
    "processed_at": "2024-11-17T10:30:00Z",
    "profile_used": null,
    "profile_confidence": 0.0
  },
  "corruption_scan": {
    "severity": "none",
    "signals": [],
    "details": []
  },
  "column_mapping": {
    "mapped": [
      {
        "supplier_column": "Art. Nr.",
        "target_field": "supplier_sku",
        "confidence": 0.87,
        "method": "hybrid",
        "scores": { "name": 0.72, "domain": 0.95, "constraint": 0.80 },
        "transform": null
      }
    ],
    "unmapped_supplier_columns": [],
    "missing_target_fields": ["lot_number"]
  },
  "rows": [
    {
      "row_index": 0,
      "raw": { "Art. Nr.": "SUP-123", "Menge": "50", "Stk-Preis": "12.50" },
      "mapped": {
        "supplier_sku": "SUP-123",
        "qty_shipped": 50.0,
        "unit_price": 12.50
      },
      "po_match": {
        "po_line_id": "line_007",
        "confidence": 1.0,
        "method": "sku_exact"
      },
      "status": "accepted",
      "warnings": []
    }
  ],
  "summary": {
    "total_rows": 10,
    "accepted": 9,
    "flagged": 1,
    "review_required": 0,
    "rejected": 0,
    "matched_to_po": 9,
    "unmatched": 1
  },
  "review_queue": []
}
```

---

### Save a confirmed supplier profile

Once you have confirmed the mapping for a supplier, save it so future files from the same supplier skip re-mapping:

```bash
curl -X POST http://localhost:8000/suppliers/ACME_CORP/profile \
  -H "Content-Type: application/json" \
  -d '{ "mapped": [...], "unmapped_supplier_columns": [], "missing_target_fields": [] }'
```

### Retrieve a saved profile

```bash
curl http://localhost:8000/suppliers/ACME_CORP/profile
```

### Health check

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

---

## Use as a Python Library

You can call the pipeline directly without running the API:

```python
from mapper.pipeline import process

result = process(
    file_path="supplier_file.xlsx",
    supplier_id="ACME_CORP",           # optional — loads saved profile if exists
    po_lines=[                          # optional — your PO line items for row linkage
        {"id": "line_001", "buyer_sku": "OUR-456", "description": "Widget A", "line_number": 1},
        {"id": "line_002", "buyer_sku": "OUR-789", "description": "Widget B", "line_number": 2},
    ],
    sku_xref={                          # optional — supplier SKU → buyer SKU lookup
        "SUP-123": "OUR-456",
        "SUP-999": "OUR-789",
    },
    reference_skus={"OUR-456", "OUR-789"},   # optional — for leading zero restoration
)

# Check for corruption warnings
if result.corruption_scan.severity == "critical":
    print("File may be corrupted — review before proceeding")

# Inspect column mappings
for mapping in result.column_mapping.mapped:
    print(f"{mapping.supplier_column} → {mapping.target_field} ({mapping.confidence:.0%})")

# Iterate accepted rows
for row in result.rows:
    if row.status == "accepted":
        print(row.mapped.supplier_sku, row.mapped.qty_shipped)

# Check what needs human review
for item in result.review_queue:
    print(f"[{item.kind}] {item.issue}")

# Save profile for next time
from mapper.profiles.profile_store import save_profile
save_profile("ACME_CORP", result.column_mapping)
```

---

## Target Fields

These are the canonical fields every supplier file is mapped to:

| Field | Description |
|---|---|
| `po_number` | Purchase order number |
| `po_line_number` | Line position within the PO |
| `buyer_sku` | Your internal item code |
| `supplier_sku` | Supplier's item code |
| `description` | Item description |
| `qty_ordered` | Quantity from the original PO |
| `qty_shipped` | Quantity the supplier shipped |
| `unit_price` | Per-unit cost |
| `total_price` | Line total (qty × unit price) |
| `uom` | Unit of measure (ea, box, kg, etc.) |
| `ship_date` | Date supplier shipped (ISO format) |
| `lot_number` | Lot or batch number for traceability |

---

## Row Status Values

| Status | Meaning |
|---|---|
| `accepted` | Mapped and matched with high confidence — safe to process |
| `flagged` | Mapped and matched but has warnings (e.g. value was corrected) |
| `review_required` | Could not match to a PO line — needs human input |
| `rejected` | Unrecoverable data corruption (e.g. barcode precision lost) — must not be processed |

---

## Excel Corruption Handling

If a customer opens the supplier's CSV in Excel and saves it, values silently corrupt.
Schema Mapper detects and handles these automatically:

| Corruption | Example | Handling |
|---|---|---|
| Leading zeros stripped | `00123` → `123` | Auto-restored if reference SKU list provided |
| Barcode → scientific notation | `5901234123457` → `5.90123E+12` | Recovered via check digit; flagged as critical if digits lost |
| SKU → date serial | `1-2` → `45293` | Flagged for review in non-date columns |
| Thousands comma in quantity | `1,200` → parsed as `1` | Stripped automatically before parsing |

Files with corruption signals trigger a warning in `corruption_scan` before any mapping occurs.

---

## Supported File Formats

| Format | Notes |
|---|---|
| `.csv` | Auto-detects encoding; strips BOM |
| `.xlsx` | Reads raw cell values via openpyxl — not Excel's rendered output |
| `.xls` | Same as xlsx |
| `.pdf` | Extracts first table found per page via pdfplumber |

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Roadmap

- [ ] Persistent review queue store (database-backed)
- [ ] EDI 856 ASN format support
- [ ] Active learning: use confirmed mappings to improve classifier weights
- [ ] Multi-sheet XLSX support
- [ ] Partial shipment splitting (one supplier row → multiple PO lines)
