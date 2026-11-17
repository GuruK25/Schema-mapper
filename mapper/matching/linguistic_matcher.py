"""
Name-based linguistic matcher.
Scores supplier column headers against canonical target field names.
"""
from __future__ import annotations
from rapidfuzz import fuzz


# Canonical target fields with their known synonyms / abbreviations
TARGET_SYNONYMS: dict[str, list[str]] = {
    "po_number":      ["po", "purchase order", "order no", "order number", "ponumber", "po#", "order#"],
    "po_line_number": ["line", "line no", "line#", "lineitem", "line number", "item no", "seq"],
    "buyer_sku":      ["sku", "item code", "item#", "product code", "our sku", "buyer sku"],
    "supplier_sku":   ["supplier sku", "vendor sku", "art nr", "article", "article no", "part no", "part#", "ref"],
    "description":    ["desc", "description", "product name", "item description", "product desc", "name"],
    "qty_ordered":    ["qty ordered", "ordered qty", "order qty", "quantity ordered", "orig qty"],
    "qty_shipped":    ["qty", "quantity", "qty shipped", "shipped qty", "units shipped", "quantity shipped", "units"],
    "unit_price":     ["price", "unit price", "unit cost", "cost", "rate", "stk-preis", "einzelpreis"],
    "total_price":    ["total", "total price", "line total", "amount", "ext price", "extended price", "gesamt"],
    "uom":            ["uom", "unit", "unit of measure", "measure", "pack"],
    "ship_date":      ["ship date", "shipped date", "date shipped", "dispatch date", "shipping date"],
    "lot_number":     ["lot", "lot no", "lot number", "batch", "batch no", "serial"],
}


def score_column(supplier_header: str, target_field: str) -> float:
    """
    Returns similarity score 0.0–1.0 between a supplier header and a target field.
    Uses token-set ratio to handle word-order differences and partial matches.
    """
    header_norm = _normalize(supplier_header)
    best = 0.0

    for synonym in [target_field] + TARGET_SYNONYMS.get(target_field, []):
        s = fuzz.token_set_ratio(header_norm, _normalize(synonym)) / 100.0
        if s > best:
            best = s
        if best == 1.0:
            break

    return round(best, 3)


def rank_targets(supplier_header: str) -> list[tuple[str, float]]:
    """
    Returns all target fields ranked by similarity score, highest first.
    """
    scores = [(field, score_column(supplier_header, field)) for field in TARGET_SYNONYMS]
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores


def _normalize(text: str) -> str:
    return text.lower().replace("_", " ").replace("-", " ").replace("#", " ").strip()
