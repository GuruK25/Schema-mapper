"""
Name-based linguistic matcher.
Scores supplier column headers against fields in a caller-provided TargetSchema.
No hardcoded field names — everything comes from the schema.
"""
from __future__ import annotations
from rapidfuzz import fuzz
from mapper.models import TargetSchema


def score_column(supplier_header: str, target_field_name: str, schema: TargetSchema) -> float:
    """
    Returns similarity score 0.0–1.0 between a supplier header and one target field.
    Matches against the field's name, description, and synonyms.
    """
    field = _get_field(target_field_name, schema)
    if field is None:
        return 0.0

    header_norm = _normalize(supplier_header)
    candidates = [field.name, field.description] + field.synonyms
    candidates = [c for c in candidates if c]

    best = 0.0
    for candidate in candidates:
        s = fuzz.token_set_ratio(header_norm, _normalize(candidate)) / 100.0
        if s > best:
            best = s
        if best == 1.0:
            break

    return round(best, 3)


def rank_targets(supplier_header: str, schema: TargetSchema) -> list[tuple[str, float]]:
    """
    Returns all target fields ranked by similarity score, highest first.
    """
    scores = [
        (field.name, score_column(supplier_header, field.name, schema))
        for field in schema.fields
    ]
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores


def _get_field(name: str, schema: TargetSchema):
    for f in schema.fields:
        if f.name == name:
            return f
    return None


def _normalize(text: str) -> str:
    return text.lower().replace("_", " ").replace("-", " ").replace("#", " ").strip()
