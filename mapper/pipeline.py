"""
Main pipeline — orchestrates all stages in order.
Accepts any TargetSchema — not tied to PO line items or any specific domain.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mapper.models import (
    FieldType, FileMetadata, MappingResult, MappedRow,
    RecordMatch, Summary, ReviewItem, TargetSchema, Warning,
)
from mapper.ingestion.reader import read_file
from mapper.sanitize.fingerprint import scan_file
from mapper.sanitize.sanitizers import sanitize_sku, sanitize_barcode, sanitize_numeric
from mapper.matching.hybrid_scorer import map_columns, ACCEPT_THRESHOLD, REVIEW_THRESHOLD
from mapper.linkage.record_linker import link_rows
from mapper.profiles.profile_store import load_profile, profile_confidence, save_profile


def process(
    file_path: str | Path,
    target_schema: TargetSchema,
    source_id: str | None = None,          # e.g. supplier ID, sender ID
    records: list[dict] | None = None,     # target system records to match rows against
    exact_keys: list[str] | None = None,   # fields to exact-match on
    fuzzy_keys: list[str] | None = None,   # fields to fuzzy-match on
    key_xref: dict[str, str] | None = None,  # source_value → target_value lookup
    reference_values: set[str] | None = None, # valid values for leading-zero restoration
    confirm_and_save_profile: bool = False,
) -> MappingResult:
    path = Path(file_path)
    records   = records   or []
    key_xref  = key_xref  or {}
    exact_keys = exact_keys or []
    fuzzy_keys  = fuzzy_keys  or []

    # Stage 0 — corruption fingerprint
    corruption = scan_file(path)

    # Stage 1 — raw ingest
    headers, rows = read_file(path)

    # Stage 2 — load supplier profile if available
    profile_used = None
    profile_conf = 0.0
    column_mapping = None
    if source_id:
        stored = load_profile(source_id)
        if stored:
            conf = profile_confidence(stored, headers)
            if conf >= 0.8:
                column_mapping = stored
                profile_used = source_id
                profile_conf = conf

    # Stage 3 — hybrid column mapping (if no profile hit)
    if column_mapping is None:
        column_mapping = map_columns(headers, rows, target_schema)

    # Stage 4 — build MappedRows
    mapped_rows = _apply_mapping(rows, column_mapping, target_schema, reference_values)

    # Stage 5 — record linkage (optional)
    if records:
        mapped_rows = link_rows(
            mapped_rows, records,
            exact_keys=exact_keys,
            fuzzy_keys=fuzzy_keys,
            key_xref=key_xref,
        )

    # Stage 6 — assign statuses and build review queue
    review_queue: list[ReviewItem] = []
    _assign_statuses(mapped_rows, column_mapping, review_queue, bool(records))

    # Stage 7 — save profile if confirmed
    if confirm_and_save_profile and source_id:
        save_profile(source_id, column_mapping)

    return MappingResult(
        metadata=FileMetadata(
            file_name=path.name,
            source_id=source_id,
            processed_at=datetime.now(timezone.utc).isoformat(),
            profile_used=profile_used,
            profile_confidence=profile_conf,
        ),
        target_schema=target_schema,
        corruption_scan=corruption,
        column_mapping=column_mapping,
        rows=mapped_rows,
        summary=_build_summary(mapped_rows),
        review_queue=review_queue,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _apply_mapping(
    rows: list[dict[str, str]],
    column_mapping,
    schema: TargetSchema,
    reference_values: set[str] | None,
) -> list[MappedRow]:
    col_map = {m.supplier_column: m for m in column_mapping.mapped}
    field_map = {f.name: f for f in schema.fields}

    result = []
    for idx, raw_row in enumerate(rows):
        mapped: dict[str, Any] = {}
        warnings: list[Warning] = []

        for supplier_col, mapping in col_map.items():
            raw_val = raw_row.get(supplier_col, "")
            field   = field_map.get(mapping.target_field)
            if field is None:
                mapped[mapping.target_field] = raw_val
                continue

            clean_val, warn = _sanitize(raw_val, field, reference_values)
            if warn:
                warn.field = field.name
                warnings.append(warn)

            if clean_val is not None and clean_val != "":
                mapped[field.name] = clean_val

        result.append(MappedRow(
            row_index=idx,
            raw=raw_row,
            mapped=mapped,
            status="flagged" if warnings else "accepted",
            warnings=warnings,
        ))

    return result


def _sanitize(raw: str, field, reference_values):
    hint = field.domain_hint or ""

    if hint == "barcode":
        return sanitize_barcode(raw)
    if hint == "sku":
        return sanitize_sku(raw, reference_values)
    if field.type == FieldType.number or hint in ("qty", "unit_price", "total_price"):
        num, warn = sanitize_numeric(raw)
        return (num if num is not None else raw), warn
    return raw, None


def _assign_statuses(
    mapped_rows: list[MappedRow],
    column_mapping,
    review_queue: list[ReviewItem],
    has_records: bool,
) -> None:
    for row in mapped_rows:
        critical = any(w.severity == "critical" for w in row.warnings)
        no_match = has_records and not row.record_match.record_id

        if critical:
            row.status = "rejected"
            review_queue.append(ReviewItem(
                kind="value_corruption",
                row_index=row.row_index,
                issue=next(w.message for w in row.warnings if w.severity == "critical"),
            ))
        elif no_match:
            row.status = "review_required"
            review_queue.append(ReviewItem(
                kind="row_match",
                row_index=row.row_index,
                issue=f"Row {row.row_index}: no matching record found",
            ))

    for m in column_mapping.mapped:
        if m.confidence < ACCEPT_THRESHOLD:
            review_queue.append(ReviewItem(
                kind="column_mapping",
                supplier_column=m.supplier_column,
                target_field=m.target_field,
                current_value=str(round(m.confidence, 2)),
                issue=f"Low-confidence mapping ({m.confidence:.0%}): {m.supplier_column} → {m.target_field}",
            ))


def _build_summary(rows: list[MappedRow]) -> Summary:
    s = Summary(total_rows=len(rows))
    for row in rows:
        match row.status:
            case "accepted":        s.accepted += 1
            case "flagged":         s.flagged += 1
            case "review_required": s.review_required += 1
            case "rejected":        s.rejected += 1
        if row.record_match.record_id:
            s.matched_to_record += 1
        else:
            s.unmatched += 1
    return s
