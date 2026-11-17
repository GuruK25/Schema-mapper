"""
Instance-based domain classifier.
Inspects column values to determine their semantic domain.
"""
from __future__ import annotations
import re
from collections import Counter


DOMAINS = [
    "sku", "barcode", "po_number", "po_line_number",
    "qty", "unit_price", "total_price",
    "uom", "date", "description", "lot_number", "unknown",
]

# Patterns used for rule-based classification
_BARCODE_RE = re.compile(r"^\d{8}$|^\d{12,14}$")
_DATE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}$"
    r"|^\d{1,2}/\d{1,2}/\d{2,4}$"
    r"|^\d{1,2}-\d{1,2}-\d{2,4}$"
)
_UOM_VALUES = {"ea", "each", "pc", "pcs", "box", "case", "kg", "lb", "lbs", "m", "ft", "l", "unit", "units"}
_PO_RE = re.compile(r"^(po|purchase.?order)?[-_]?\d{4,}$", re.IGNORECASE)


def classify_column(values: list[str]) -> tuple[str, float]:
    """
    Returns (domain, confidence) for a column given its sample values.
    Drops empty values before classifying.
    """
    samples = [v.strip() for v in values if v.strip()]
    if not samples:
        return "unknown", 0.0

    votes: Counter = Counter()

    for val in samples:
        domain = _classify_value(val)
        votes[domain] += 1

    top_domain, top_count = votes.most_common(1)[0]
    confidence = top_count / len(samples)
    return top_domain, round(confidence, 3)


def _classify_value(val: str) -> str:
    # Barcode — 8, 12, 13, 14 digit numbers
    if _BARCODE_RE.match(val):
        return "barcode"

    # Date
    if _DATE_RE.match(val):
        return "date"

    # UOM
    if val.lower() in _UOM_VALUES:
        return "uom"

    # PO number
    if _PO_RE.match(val):
        return "po_number"

    # Numeric — could be qty, price, or line number
    try:
        num = float(val.replace(",", ""))
        if num == int(num) and 1 <= num <= 9999:
            return "qty"           # small integer → likely qty or line number
        if num > 0:
            return "unit_price"    # decimal or large → likely price
    except ValueError:
        pass

    # Short alpha-numeric with dashes/underscores → SKU
    if re.match(r"^[A-Z0-9][A-Z0-9\-_]{2,19}$", val, re.IGNORECASE):
        return "sku"

    # Long free text → description
    if len(val) > 20:
        return "description"

    return "unknown"
