"""
Record linker — matches supplier rows to PO line items.
"""
from __future__ import annotations
from rapidfuzz import fuzz
from mapper.models import MappedRow, MappedValues, PoMatch


def link_rows(
    rows: list[MappedRow],
    po_lines: list[dict],           # list of PO line items from the system
    sku_xref: dict[str, str],       # supplier_sku → buyer_sku cross-reference
) -> list[MappedRow]:
    """
    Attempts to match each MappedRow to a PO line item.
    Updates row.po_match in place and returns the list.
    """
    for row in rows:
        match = _find_match(row.mapped, po_lines, sku_xref)
        row.po_match = match
        if match.po_line_id:
            row.mapped.buyer_sku = row.mapped.buyer_sku or _resolve_buyer_sku(
                row.mapped.supplier_sku, sku_xref
            )
    return rows


def _find_match(
    mapped: MappedValues,
    po_lines: list[dict],
    sku_xref: dict[str, str],
) -> PoMatch:
    # Strategy 1: exact SKU lookup via cross-reference
    buyer_sku = _resolve_buyer_sku(mapped.supplier_sku, sku_xref) or mapped.buyer_sku
    if buyer_sku:
        for line in po_lines:
            if line.get("buyer_sku") == buyer_sku:
                return PoMatch(po_line_id=line["id"], confidence=1.0, method="sku_exact")

    # Strategy 2: zero-padded SKU variants
    if mapped.supplier_sku:
        for length in range(len(mapped.supplier_sku) + 1, 15):
            padded = mapped.supplier_sku.zfill(length)
            resolved = sku_xref.get(padded)
            if resolved:
                for line in po_lines:
                    if line.get("buyer_sku") == resolved:
                        return PoMatch(po_line_id=line["id"], confidence=0.9, method="sku_padded")

    # Strategy 3: PO line number direct match
    if mapped.po_line_number is not None:
        for line in po_lines:
            if str(line.get("line_number")) == str(mapped.po_line_number):
                return PoMatch(po_line_id=line["id"], confidence=0.85, method="po_line_number")

    # Strategy 4: fuzzy description match
    if mapped.description:
        best_id, best_score = None, 0.0
        for line in po_lines:
            score = fuzz.token_set_ratio(mapped.description, line.get("description", "")) / 100.0
            if score > best_score:
                best_score, best_id = score, line["id"]
        if best_score >= 0.75:
            return PoMatch(po_line_id=best_id, confidence=round(best_score, 3), method="description_fuzzy")

    return PoMatch(po_line_id=None, confidence=0.0, method=None)


def _resolve_buyer_sku(supplier_sku: str | None, xref: dict[str, str]) -> str | None:
    if not supplier_sku:
        return None
    return xref.get(supplier_sku)
