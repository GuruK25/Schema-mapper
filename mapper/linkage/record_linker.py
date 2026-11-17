"""
Generic record linker.
Matches mapped rows against any list of target records — not tied to PO line items.
Caller controls which fields to match on.
"""
from __future__ import annotations
from rapidfuzz import fuzz
from mapper.models import MappedRow, RecordMatch


def link_rows(
    rows: list[MappedRow],
    records: list[dict],
    exact_keys: list[str],       # fields to try exact match on (e.g. ["buyer_sku"])
    fuzzy_keys: list[str],       # fields to try fuzzy match on (e.g. ["description"])
    key_xref: dict[str, str] | None = None,  # source_value → target_value lookup
    id_field: str = "id",        # the field in records[] that holds the record's identifier
    fuzzy_threshold: float = 0.75,
) -> list[MappedRow]:
    """
    Attempts to match each MappedRow to a record in the caller's target list.
    Updates row.record_match and returns the list.
    """
    key_xref = key_xref or {}

    for row in rows:
        row.record_match = _find_match(
            row.mapped, records, exact_keys, fuzzy_keys,
            key_xref, id_field, fuzzy_threshold,
        )

    return rows


def _find_match(
    mapped: dict,
    records: list[dict],
    exact_keys: list[str],
    fuzzy_keys: list[str],
    key_xref: dict[str, str],
    id_field: str,
    fuzzy_threshold: float,
) -> RecordMatch:

    # Strategy 1: exact match on each exact_key (after optional xref lookup)
    for key in exact_keys:
        source_val = mapped.get(key)
        if not source_val:
            continue
        target_val = key_xref.get(str(source_val), str(source_val))
        for rec in records:
            if str(rec.get(key, "")) == target_val:
                return RecordMatch(
                    record_id=str(rec.get(id_field, "")),
                    confidence=1.0,
                    method="exact",
                )

    # Strategy 2: xref-only match (source key ≠ target key naming)
    for source_val, target_val in key_xref.items():
        for key in exact_keys:
            if str(mapped.get(key, "")) == source_val:
                for rec in records:
                    if str(rec.get(key, "")) == target_val:
                        return RecordMatch(
                            record_id=str(rec.get(id_field, "")),
                            confidence=0.9,
                            method="key_xref",
                        )

    # Strategy 3: fuzzy match on fuzzy_keys
    best_id, best_score = None, 0.0
    for key in fuzzy_keys:
        source_val = str(mapped.get(key, ""))
        if not source_val:
            continue
        for rec in records:
            score = fuzz.token_set_ratio(source_val, str(rec.get(key, ""))) / 100.0
            if score > best_score:
                best_score = score
                best_id = str(rec.get(id_field, ""))

    if best_score >= fuzzy_threshold:
        return RecordMatch(
            record_id=best_id,
            confidence=round(best_score, 3),
            method="fuzzy",
        )

    return RecordMatch(record_id=None, confidence=0.0, method=None)
