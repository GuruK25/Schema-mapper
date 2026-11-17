"""
Hybrid column mapping scorer.
Combines linguistic name score + domain classifier score + constraint signals.
Domain-to-field mapping is built at runtime from the caller's TargetSchema — not hardcoded.
"""
from __future__ import annotations
from mapper.models import ColumnMapping, ColumnMappingResult, MatchScores, TargetSchema, ValueTransform
from mapper.matching.linguistic_matcher import rank_targets
from mapper.matching.domain_classifier import classify_column


WEIGHTS = {"name": 0.5, "domain": 0.4, "constraint": 0.1}

ACCEPT_THRESHOLD = 0.65
REVIEW_THRESHOLD = 0.40


def map_columns(
    headers: list[str],
    rows: list[dict[str, str]],
    schema: TargetSchema,
) -> ColumnMappingResult:
    """
    Maps supplier columns to target fields defined in the caller's schema.
    No PO-specific logic — works for any target object.
    """
    domain_hints = _build_domain_hints(schema)
    already_mapped: set[str] = set()
    mappings: list[ColumnMapping] = []
    low_confidence: list[str] = []

    for header in headers:
        samples = [row.get(header, "") for row in rows[:50]]

        domain, domain_conf = classify_column(samples)
        name_ranks = dict(rank_targets(header, schema))
        constraint_score = _constraint_score(samples, domain)

        # Candidate targets = domain-hinted fields first, then all schema fields
        hinted = domain_hints.get(domain, [])
        all_targets = list(dict.fromkeys(hinted + [f.name for f in schema.fields]))

        candidates: list[tuple[str, float, MatchScores]] = []
        for target in all_targets:
            if target in already_mapped:
                continue
            name_s = name_ranks.get(target, 0.0)
            dom_s  = domain_conf if target in hinted else 0.0
            con_s  = constraint_score
            combined = (
                WEIGHTS["name"]       * name_s
                + WEIGHTS["domain"]   * dom_s
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

    all_target_names = {f.name for f in schema.fields}
    mapped_names = {m.target_field for m in mappings}
    required_missing = [
        f.name for f in schema.fields
        if f.required and f.name not in mapped_names
    ]

    return ColumnMappingResult(
        mapped=mappings,
        unmapped_supplier_columns=low_confidence,
        missing_target_fields=sorted(all_target_names - mapped_names),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_domain_hints(schema: TargetSchema) -> dict[str, list[str]]:
    """
    Build a domain → [target_field_names] map from the schema's domain_hints and types.
    Caller sets domain_hint on a TargetField to give the classifier a boost.
    Falls back to type-based inference when no hint is given.
    """
    hints: dict[str, list[str]] = {}

    for field in schema.fields:
        domains: list[str] = []

        if field.domain_hint:
            domains = [field.domain_hint]
        else:
            # Infer from type
            match field.type.value:
                case "number":  domains = ["qty", "unit_price", "total_price"]
                case "date":    domains = ["date"]
                case "string":  domains = ["sku", "description", "barcode", "lot_number"]
                case _:         domains = []

        for d in domains:
            hints.setdefault(d, [])
            if field.name not in hints[d]:
                hints[d].append(field.name)

    return hints


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
