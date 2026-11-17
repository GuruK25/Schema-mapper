"""
Hybrid column mapping scorer.
Combines linguistic name score + domain classifier score + constraint signals.
"""
from __future__ import annotations
from mapper.models import ColumnMapping, ColumnMappingResult, MatchScores, ValueTransform
from mapper.matching.linguistic_matcher import rank_targets
from mapper.matching.domain_classifier import classify_column, DOMAINS


# Maps classifier domain → target fields it supports (ordered by priority)
DOMAIN_TO_TARGETS: dict[str, list[str]] = {
    "sku":          ["buyer_sku", "supplier_sku"],
    "barcode":      ["buyer_sku", "supplier_sku"],
    "po_number":    ["po_number"],
    "po_line_number": ["po_line_number"],
    "qty":          ["qty_shipped", "qty_ordered"],
    "unit_price":   ["unit_price", "total_price"],
    "total_price":  ["total_price", "unit_price"],
    "uom":          ["uom"],
    "date":         ["ship_date"],
    "description":  ["description"],
    "lot_number":   ["lot_number"],
    "unknown":      [],
}

WEIGHTS = {"name": 0.5, "domain": 0.4, "constraint": 0.1}

# Confidence thresholds
ACCEPT_THRESHOLD = 0.65
REVIEW_THRESHOLD = 0.40


def map_columns(
    headers: list[str],
    rows: list[dict[str, str]],
) -> ColumnMappingResult:
    """
    Given supplier headers and row data, return the best column mapping.
    """
    all_targets = list(DOMAIN_TO_TARGETS.keys())
    already_mapped: set[str] = set()

    mappings: list[ColumnMapping] = []
    low_confidence: list[str] = []

    for header in headers:
        samples = [row.get(header, "") for row in rows[:50]]

        domain, domain_conf = classify_column(samples)
        name_ranks = dict(rank_targets(header))
        constraint_score = _constraint_score(samples, domain)

        # Score every target field
        candidates: list[tuple[str, float, MatchScores]] = []
        for target in DOMAIN_TO_TARGETS.get(domain, []) + list(name_ranks.keys()):
            if target in already_mapped:
                continue
            name_s = name_ranks.get(target, 0.0)
            dom_s = domain_conf if target in DOMAIN_TO_TARGETS.get(domain, []) else 0.0
            con_s = constraint_score
            combined = (
                WEIGHTS["name"] * name_s
                + WEIGHTS["domain"] * dom_s
                + WEIGHTS["constraint"] * con_s
            )
            candidates.append((target, combined, MatchScores(name=name_s, domain=dom_s, constraint=con_s)))

        if not candidates:
            low_confidence.append(header)
            continue

        candidates.sort(key=lambda x: x[1], reverse=True)
        best_target, best_score, best_scores = candidates[0]

        if best_score < REVIEW_THRESHOLD:
            low_confidence.append(header)
            continue

        already_mapped.add(best_target)
        mappings.append(ColumnMapping(
            supplier_column=header,
            target_field=best_target,
            confidence=round(best_score, 3),
            method="hybrid",
            scores=best_scores,
            transform=_infer_transform(domain, samples),
        ))

    all_target_fields = {t for targets in DOMAIN_TO_TARGETS.values() for t in targets}
    mapped_targets = {m.target_field for m in mappings}

    return ColumnMappingResult(
        mapped=mappings,
        unmapped_supplier_columns=low_confidence,
        missing_target_fields=sorted(all_target_fields - mapped_targets),
    )


def _constraint_score(samples: list[str], domain: str) -> float:
    if not samples:
        return 0.0
    non_empty = [s for s in samples if s.strip()]
    if not non_empty:
        return 0.0
    unique_ratio = len(set(non_empty)) / len(non_empty)
    if domain in ("sku", "barcode", "po_number"):
        return min(unique_ratio, 1.0)
    return 0.5


def _infer_transform(domain: str, samples: list[str]) -> ValueTransform | None:
    if domain == "date":
        fmt = _detect_date_format(samples)
        if fmt:
            return ValueTransform(type="date_parse", params={"from_format": fmt})
    if domain in ("qty", "unit_price", "total_price"):
        if any("," in s for s in samples):
            return ValueTransform(type="numeric_clean", params={})
    return None


def _detect_date_format(samples: list[str]) -> str | None:
    import re
    for s in samples:
        if re.match(r"\d{4}-\d{2}-\d{2}", s):
            return "YYYY-MM-DD"
        if re.match(r"\d{1,2}/\d{1,2}/\d{4}", s):
            return "MM/DD/YYYY"
        if re.match(r"\d{1,2}-\d{1,2}-\d{4}", s):
            return "MM-DD-YYYY"
    return None
