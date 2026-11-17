from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Value transform
# ---------------------------------------------------------------------------

class ValueTransform(BaseModel):
    type: Literal["date_parse", "numeric_clean", "zero_pad", "unit_convert", "code_lookup"]
    params: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Corruption scan
# ---------------------------------------------------------------------------

class CorruptionDetail(BaseModel):
    column: str
    type: Literal["leading_zero", "scientific_notation", "date_coercion", "thousands_comma"]
    affected_rows: list[int] = Field(default_factory=list)
    recoverable: bool


class CorruptionScan(BaseModel):
    severity: Literal["none", "warn", "critical"]
    signals: list[str] = Field(default_factory=list)
    details: list[CorruptionDetail] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Column mapping
# ---------------------------------------------------------------------------

class MatchScores(BaseModel):
    name: float = 0.0
    domain: float = 0.0
    constraint: float = 0.0


class ColumnMapping(BaseModel):
    supplier_column: str
    target_field: str
    confidence: float
    method: Literal["profile", "linguistic", "instance", "hybrid"]
    scores: MatchScores
    transform: ValueTransform | None = None


class ColumnMappingResult(BaseModel):
    mapped: list[ColumnMapping] = Field(default_factory=list)
    unmapped_supplier_columns: list[str] = Field(default_factory=list)
    missing_target_fields: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Row-level results
# ---------------------------------------------------------------------------

class Warning(BaseModel):
    severity: Literal["info", "warn", "critical"]
    type: Literal[
        "leading_zero_restored",
        "barcode_unrecoverable",
        "date_coercion",
        "thousands_comma",
        "low_confidence_mapping",
        "no_po_match",
    ]
    field: str
    original_value: str
    resolved_value: str | None = None
    message: str


class MappedValues(BaseModel):
    po_number: str | None = None
    po_line_number: int | None = None
    buyer_sku: str | None = None
    supplier_sku: str | None = None
    description: str | None = None
    qty_ordered: float | None = None
    qty_shipped: float | None = None
    unit_price: float | None = None
    total_price: float | None = None
    uom: str | None = None
    ship_date: str | None = None      # ISO date string
    lot_number: str | None = None


class PoMatch(BaseModel):
    po_line_id: str | None = None
    confidence: float = 0.0
    method: Literal[
        "sku_exact", "sku_padded", "description_fuzzy", "po_line_number"
    ] | None = None


class MappedRow(BaseModel):
    row_index: int
    raw: dict[str, str] = Field(default_factory=dict)
    mapped: MappedValues = Field(default_factory=MappedValues)
    po_match: PoMatch = Field(default_factory=PoMatch)
    status: Literal["accepted", "flagged", "review_required", "rejected"]
    warnings: list[Warning] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Review queue
# ---------------------------------------------------------------------------

class ReviewItem(BaseModel):
    kind: Literal["column_mapping", "row_match", "value_corruption"]
    row_index: int | None = None
    supplier_column: str | None = None
    target_field: str | None = None
    current_value: str | None = None
    issue: str
    options: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Metadata & summary
# ---------------------------------------------------------------------------

class FileMetadata(BaseModel):
    file_name: str
    supplier_id: str | None = None
    po_number: str | None = None
    processed_at: str                 # ISO datetime
    profile_used: str | None = None
    profile_confidence: float = 0.0


class Summary(BaseModel):
    total_rows: int = 0
    accepted: int = 0
    flagged: int = 0
    review_required: int = 0
    rejected: int = 0
    matched_to_po: int = 0
    unmatched: int = 0


# ---------------------------------------------------------------------------
# Top-level result
# ---------------------------------------------------------------------------

class MappingResult(BaseModel):
    metadata: FileMetadata
    corruption_scan: CorruptionScan
    column_mapping: ColumnMappingResult
    rows: list[MappedRow] = Field(default_factory=list)
    summary: Summary = Field(default_factory=Summary)
    review_queue: list[ReviewItem] = Field(default_factory=list)
