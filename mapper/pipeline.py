"""
Main pipeline — orchestrates all stages in order.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path

from mapper.models import (
    FileMetadata, MappingResult, MappedRow, MappedValues,
    Summary, ReviewItem, Warning,
)
from mapper.ingestion.reader import read_file
from mapper.sanitize.fingerprint import scan_file
from mapper.sanitize.sanitizers import sanitize_sku, sanitize_barcode, sanitize_numeric
from mapper.matching.hybrid_scorer import map_columns, ACCEPT_THRESHOLD, REVIEW_THRESHOLD
from mapper.linkage.record_linker import link_rows
from mapper.profiles.profile_store import load_profile, profile_confidence, save_profile


def process(
    file_path: str | Path,
    po_lines: list[dict] | None = None,
    supplier_id: str | None = None,
    sku_xref: dict[str, str] | None = None,
    reference_skus: set[str] | None = None,
    confirm_and_save_profile: bool = False,
) -> MappingResult:
    path = Path(file_path)
    po_lines = po_lines or []
    sku_xref = sku_xref or {}

    # Stage 0 — corruption fingerprint
    corruption = scan_file(path)

    # Stage 1 — raw ingest
    headers, rows = read_file(path)

    # Stage 2 — load supplier profile if available
    profile_used = None
    profile_conf = 0.0
    column_mapping = None
    if supplier_id:
        stored = load_profile(supplier_id)
        if stored:
            conf = profile_confidence(stored, headers)
            if conf >= 0.8:
                column_mapping = stored
                profile_used = supplier_id
                profile_conf = conf

    # Stage 3 — hybrid column mapping (if no profile hit)
    if column_mapping is None:
        column_mapping = map_columns(headers, rows)

    # Stage 4 — build MappedRows
    mapped_rows = _apply_mapping(rows, column_mapping, reference_skus)

    # Stage 5 — record linkage
    if po_lines:
        mapped_rows = link_rows(mapped_rows, po_lines, sku_xref)

    # Stage 6 — assign statuses and build review queue
    review_queue: list[ReviewItem] = []
    _assign_statuses(mapped_rows, column_mapping, review_queue)

    # Stage 7 — save profile if confirmed
    if confirm_and_save_profile and supplier_id:
        save_profile(supplier_id, column_mapping)

    summary = _build_summary(mapped_rows)

    return MappingResult(
        metadata=FileMetadata(
            file_name=path.name,
            supplier_id=supplier_id,
            processed_at=datetime.now(timezone.utc).isoformat(),
            profile_used=profile_used,
            profile_confidence=profile_conf,
        ),
        corruption_scan=corruption,
        column_mapping=column_mapping,
        rows=mapped_rows,
        summary=summary,
        review_queue=review_queue,
    )


def _apply_mapping(
    rows: list[dict[str, str]],
    column_mapping,
    reference_skus: set[str] | None,
) -> list[MappedRow]:
    col_map = {m.supplier_column: m for m in column_mapping.mapped}
    result = []

    for idx, raw_row in enumerate(rows):
        mapped_values = MappedValues()
        warnings: list[Warning] = []

        for supplier_col, mapping in col_map.items():
            raw_val = raw_row.get(supplier_col, "")
            field = mapping.target_field

            clean_val, warn = _sanitize_value(raw_val, field, reference_skus)
            if warn:
                warn.field = field
                warnings.append(warn)

            _set_field(mapped_values, field, clean_val)

        result.append(MappedRow(
            row_index=idx,
            raw=raw_row,
            mapped=mapped_values,
            status="flagged" if warnings else "accepted",
            warnings=warnings,
        ))

    return result


def _sanitize_value(raw: str, field: str, reference_skus):
    if field in ("buyer_sku", "supplier_sku"):
        return sanitize_sku(raw, reference_skus)
    if field == "barcode":
        return sanitize_barcode(raw)
    if field in ("qty_shipped", "qty_ordered", "unit_price", "total_price"):
        num, warn = sanitize_numeric(raw)
        return (num if num is not None else raw), warn
    return raw, None


def _set_field(mv: MappedValues, field: str, value):
    if hasattr(mv, field) and value is not None and value != "":
        setattr(mv, field, value)


def _assign_statuses(mapped_rows: list[MappedRow], column_mapping, review_queue: list[ReviewItem]):
    for row in mapped_rows:
        critical = any(w.severity == "critical" for w in row.warnings)
        no_match = not row.po_match.po_line_id

        if critical:
            row.status = "rejected"
            review_queue.append(ReviewItem(
                kind="value_corruption",
                row_index=row.row_index,
                issue=next(w.message for w in row.warnings if w.severity == "critical"),
            ))
        elif no_match and row.mapped.supplier_sku:
            row.status = "review_required"
            review_queue.append(ReviewItem(
                kind="row_match",
                row_index=row.row_index,
                current_value=row.mapped.supplier_sku,
                issue=f"No PO line matched for supplier SKU: {row.mapped.supplier_sku}",
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
            case "accepted":  s.accepted += 1
            case "flagged":   s.flagged += 1
            case "review_required": s.review_required += 1
            case "rejected":  s.rejected += 1
        if row.po_match.po_line_id:
            s.matched_to_po += 1
        else:
            s.unmatched += 1
    return s
