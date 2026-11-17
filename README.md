# Schema Mapper

A Python library and REST API that reads files in **any format or structure** and maps the data to **whatever target schema you define** — automatically.

You tell it what fields you want. It figures out which supplier column maps to which field, transforms the values, and links each row to a matching record in your system. Works for purchase orders, inventory receipts, invoices, shipments, or any other domain.

---

## What It Does

```
Your file (CSV / XLSX / PDF)  +  Your target schema
              ↓
 ┌───────────────────────────────────────────────────┐
 │ 1. Fingerprint    Detect Excel-opened corruption  │
 │ 2. Ingest         Read all values as raw strings  │
 │ 3. Sanitize       Fix leading zeros, sci notation │
 │ 4. Map columns    Match headers → your fields     │
 │ 5. Link rows      Match rows → your records       │
 │ 6. Score          Flag low-confidence for review  │
 └───────────────────────────────────────────────────┘
              ↓
        MappingResult (JSON)
```

**Example:** a supplier sends a file with columns `Art. Nr.`, `Menge`, `Stk-Preis`, `Gesamt`.
You define a schema with fields `item_code`, `qty_received`, `unit_cost`, `line_total`.
Schema Mapper maps them automatically — even with no prior configuration.

---

## The Core Concept: TargetSchema

You define the fields you want to map **to**. The mapper uses this to drive everything — column matching, sanitization, record linkage, and the output shape.

```json
{
  "fields": [
    {
      "name": "item_code",
      "type": "string",
      "domain_hint": "sku",
      "synonyms": ["art nr", "article", "part no", "ref", "product code"],
      "description": "Supplier's item identifier",
      "required": true
    },
    {
      "name": "qty_received",
      "type": "number",
      "domain_hint": "qty",
      "synonyms": ["quantity", "units", "menge", "qty shipped"],
      "description": "Number of units delivered"
    },
    {
      "name": "unit_cost",
      "type": "number",
      "domain_hint": "unit_price",
      "synonyms": ["price", "unit price", "stk-preis", "cost", "rate"]
    },
    {
      "name": "delivery_date",
      "type": "date",
      "synonyms": ["ship date", "despatch date", "shipped", "date"]
    }
  ]
}
```

### TargetField properties

| Property | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Key in the output `mapped` dict |
| `type` | `string` \| `number` \| `date` \| `boolean` | No | Data type — drives sanitization |
| `synonyms` | string[] | No | Known alternative header names from your suppliers |
| `description` | string | No | Used for semantic similarity matching |
| `domain_hint` | string | No | Boosts classifier: `sku`, `barcode`, `qty`, `unit_price`, `total_price`, `date`, `description`, `lot_number` |
| `required` | boolean | No | Flags the field as missing if not found in the file |

---

## Project Structure

```
Schema-mapper/
├── mapper/                     # Core library
│   ├── models.py               # All Pydantic types: TargetSchema, MappingResult, etc.
│   ├── pipeline.py             # Main entry point — orchestrates all stages
│   ├── ingestion/
│   │   └── reader.py           # Format-agnostic file reader (CSV, XLSX, PDF)
│   ├── sanitize/
│   │   ├── fingerprint.py      # Excel corruption detector
│   │   └── sanitizers.py       # Per-field value fixers
│   ├── matching/
│   │   ├── domain_classifier.py    # Classifies columns by their data values
│   │   ├── linguistic_matcher.py   # Fuzzy synonym matching using your schema
│   │   └── hybrid_scorer.py        # Combines both into a ranked confidence score
│   ├── linkage/
│   │   └── record_linker.py    # Matches rows → your target records
│   └── profiles/
│       └── profile_store.py    # Save/load confirmed per-source mappings
├── api/                        # FastAPI REST service
│   ├── main.py
│   └── routes/
│       ├── upload.py           # POST /map
│       ├── profiles.py         # GET/POST /suppliers/{id}/profile
│       └── review.py           # GET /review
├── tests/
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
#    Linux / macOS:
source .venv/bin/activate
#    Windows:
.venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt
```

---

## Run the API

```bash
uvicorn api.main:app --reload
```

API running at **http://localhost:8000**
Interactive docs: **http://localhost:8000/docs**

---

## API Usage

### POST `/map` — map a file to your schema

Send your file and your target schema together. The schema tells the mapper what fields to produce.

```bash
curl -X POST http://localhost:8000/map \
  -F "file=@delivery_note.csv" \
  -F 'target_schema={
        "fields": [
          {"name": "item_code",    "type": "string", "domain_hint": "sku",        "synonyms": ["art nr", "part no", "ref"]},
          {"name": "qty_received", "type": "number", "domain_hint": "qty",        "synonyms": ["quantity", "units", "menge"]},
          {"name": "unit_cost",    "type": "number", "domain_hint": "unit_price", "synonyms": ["price", "stk-preis"]},
          {"name": "ship_date",    "type": "date",                                "synonyms": ["date", "despatch"]}
        ]
      }' \
  -F "source_id=SUPPLIER_ACME"
```

**With record linkage** — pass the fields to match rows against your system's records:

```bash
curl -X POST http://localhost:8000/map \
  -F "file=@packing_slip.xlsx" \
  -F 'target_schema={"fields": [...]}' \
  -F "source_id=ACME_CORP" \
  -F "exact_keys=item_code" \
  -F "fuzzy_keys=description"
```

**Form fields:**

| Field | Required | Description |
|---|---|---|
| `file` | Yes | The file to map (CSV, XLSX, PDF) |
| `target_schema` | Yes | JSON string defining your target fields (see above) |
| `source_id` | No | Source identifier — used to load/save mapping profiles |
| `exact_keys` | No | Comma-separated field names to exact-match records on |
| `fuzzy_keys` | No | Comma-separated field names to fuzzy-match records on |

**Response:**

```json
{
  "metadata": {
    "file_name": "delivery_note.csv",
    "source_id": "SUPPLIER_ACME",
    "processed_at": "2024-11-17T10:30:00Z",
    "profile_used": null,
    "profile_confidence": 0.0
  },
  "target_schema": {
    "fields": [
      {"name": "item_code", "type": "string", "domain_hint": "sku", "synonyms": ["art nr", "part no", "ref"], ...}
    ]
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
        "target_field": "item_code",
        "confidence": 0.87,
        "method": "hybrid",
        "scores": {"name": 0.72, "domain": 0.95, "constraint": 0.80},
        "transform": null
      },
      {
        "supplier_column": "Menge",
        "target_field": "qty_received",
        "confidence": 0.91,
        "method": "hybrid",
        "scores": {"name": 0.65, "domain": 1.0, "constraint": 0.5},
        "transform": null
      }
    ],
    "unmapped_supplier_columns": [],
    "missing_target_fields": ["ship_date"]
  },
  "rows": [
    {
      "row_index": 0,
      "raw": {"Art. Nr.": "SUP-123", "Menge": "50", "Stk-Preis": "12.50"},
      "mapped": {
        "item_code": "SUP-123",
        "qty_received": 50.0,
        "unit_cost": 12.5
      },
      "record_match": {
        "record_id": "rec_007",
        "confidence": 1.0,
        "method": "exact"
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
    "matched_to_record": 9,
    "unmatched": 1
  },
  "review_queue": []
}
```

---

### GET `/suppliers/{source_id}/profile`

Retrieve a saved mapping profile for a source.

```bash
curl http://localhost:8000/suppliers/ACME_CORP/profile
```

### POST `/suppliers/{source_id}/profile`

Save a confirmed mapping for a source so future files skip re-mapping.

```bash
curl -X POST http://localhost:8000/suppliers/ACME_CORP/profile \
  -H "Content-Type: application/json" \
  -d '{"mapped": [...], "unmapped_supplier_columns": [], "missing_target_fields": []}'
```

### GET `/health`

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

---

## Python Library Usage

```python
from mapper.pipeline import process
from mapper.models import TargetSchema, TargetField, FieldType

# 1. Define your target schema — any fields you want
schema = TargetSchema(fields=[
    TargetField(
        name="item_code",
        type=FieldType.string,
        domain_hint="sku",
        synonyms=["art nr", "article", "part no", "ref", "product code"],
        required=True,
    ),
    TargetField(
        name="qty_received",
        type=FieldType.number,
        domain_hint="qty",
        synonyms=["quantity", "units", "menge", "qty shipped"],
    ),
    TargetField(
        name="unit_cost",
        type=FieldType.number,
        domain_hint="unit_price",
        synonyms=["price", "unit price", "stk-preis", "cost"],
    ),
    TargetField(
        name="delivery_date",
        type=FieldType.date,
        synonyms=["ship date", "despatch date", "date"],
    ),
])

# 2. Run the pipeline
result = process(
    file_path="supplier_file.xlsx",
    target_schema=schema,

    source_id="ACME_CORP",           # optional — loads saved profile if exists

    records=[                         # optional — your system's records to match rows against
        {"id": "rec_001", "item_code": "OUR-456", "description": "Widget A"},
        {"id": "rec_002", "item_code": "OUR-789", "description": "Widget B"},
    ],
    exact_keys=["item_code"],         # match rows by exact item_code value
    fuzzy_keys=["description"],       # fall back to fuzzy description match

    key_xref={                        # optional — map supplier values to your values
        "SUP-123": "OUR-456",
        "SUP-999": "OUR-789",
    },
    reference_values={"OUR-456", "OUR-789"},  # optional — for leading zero restoration
)

# 3. Check for file corruption
if result.corruption_scan.severity == "critical":
    print("WARNING: file may be corrupted — review before proceeding")
    for detail in result.corruption_scan.details:
        print(f"  {detail.type} in column '{detail.column}', recoverable={detail.recoverable}")

# 4. Inspect column mappings
for mapping in result.column_mapping.mapped:
    print(f"{mapping.supplier_column:20} → {mapping.target_field:20} ({mapping.confidence:.0%})")

# Fields in the file that weren't mapped
if result.column_mapping.unmapped_supplier_columns:
    print("Unmapped supplier columns:", result.column_mapping.unmapped_supplier_columns)

# Your fields that weren't found in the file
if result.column_mapping.missing_target_fields:
    print("Missing target fields:", result.column_mapping.missing_target_fields)

# 5. Work with the rows
for row in result.rows:
    if row.status == "accepted":
        print(row.mapped)           # dict keyed by your TargetField names
        # e.g. {"item_code": "OUR-456", "qty_received": 50.0, "unit_cost": 12.5}

    elif row.status == "review_required":
        print(f"Row {row.row_index} needs review: {row.record_match}")

    elif row.status == "rejected":
        for w in row.warnings:
            if w.severity == "critical":
                print(f"Row {row.row_index} REJECTED: {w.message}")

# 6. Review queue — items needing human input
for item in result.review_queue:
    print(f"[{item.kind}] {item.issue}")

# 7. Save confirmed mapping profile for next time
from mapper.profiles.profile_store import save_profile
save_profile("ACME_CORP", result.column_mapping)
```

---

## `mapped` Output Shape

The `mapped` dict on each row uses your `TargetField.name` values as keys.
The shape is determined entirely by the schema you pass in — not hardcoded.

```python
# Schema with fields: item_code, qty_received, unit_cost
row.mapped == {
    "item_code":    "OUR-456",
    "qty_received": 50.0,
    "unit_cost":    12.5,
    # delivery_date absent if not found in the file
}
```

---

## Row Status Values

| Status | Meaning |
|---|---|
| `accepted` | Mapped and matched with high confidence — safe to process |
| `flagged` | Mapped and matched but has warnings (e.g. value was corrected) |
| `review_required` | Could not match to a record — needs human input |
| `rejected` | Unrecoverable data corruption — must not be processed |

---

## Record Match Methods

| Method | Description |
|---|---|
| `exact` | Value in `exact_keys` matched directly |
| `key_xref` | Value resolved via `key_xref` lookup then matched |
| `fuzzy` | Best fuzzy match on `fuzzy_keys` above threshold |
| `null` | No match found — row goes to review queue |

---

## Excel Corruption Handling

If a customer opens the supplier's CSV in Excel and saves it, values silently corrupt.
Schema Mapper detects and handles these automatically before mapping:

| Corruption | Example | Handling |
|---|---|---|
| Leading zeros stripped | `00123` → `123` | Auto-restored if `reference_values` provided |
| Barcode → scientific notation | `5901234123457` → `5.90123E+12` | Recovered via check digit; `rejected` if digits lost |
| SKU → date serial | `1-2` → `45293` | Flagged for review in non-date columns |
| Thousands comma in quantity | `1,200` → parsed as `1` | Stripped automatically before parsing |

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
- [ ] Partial quantity splitting (one source row → multiple target records)

---

## Academic Credits

The column mapping techniques in this project — including the taxonomy of schema matching
approaches (element-level, structure-level, instance-based, hybrid, and composite matchers)
— are based on the following foundational research paper:

> **Rahm, E., & Bernstein, P. A. (2001).**
> *A Survey of Approaches to Automatic Schema Matching.*
> The VLDB Journal — The International Journal on Very Large Data Bases, **10**(4), 334–350.
> Springer. https://doi.org/10.1007/s007780100057

This work is used for research and educational purposes to inform the design of the matching
pipeline. No code or text from the paper is reproduced here.
If you use this project in academic work, please also cite the above paper.
