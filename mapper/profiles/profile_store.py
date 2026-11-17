"""
Supplier profile store.
Saves and loads confirmed column mappings per supplier to skip re-matching.
"""
from __future__ import annotations
import json
from pathlib import Path
from mapper.models import ColumnMappingResult


PROFILES_DIR = Path(__file__).parent.parent.parent / "profiles"


def save_profile(supplier_id: str, mapping: ColumnMappingResult) -> None:
    PROFILES_DIR.mkdir(exist_ok=True)
    path = PROFILES_DIR / f"{supplier_id}.json"
    path.write_text(mapping.model_dump_json(indent=2))


def load_profile(supplier_id: str) -> ColumnMappingResult | None:
    path = PROFILES_DIR / f"{supplier_id}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return ColumnMappingResult.model_validate(data)


def profile_confidence(
    stored: ColumnMappingResult,
    headers: list[str],
) -> float:
    """
    How well do the current file's headers match the stored profile?
    Returns 0.0–1.0.
    """
    stored_cols = {m.supplier_column for m in stored.mapped}
    if not stored_cols:
        return 0.0
    matched = len(stored_cols & set(headers))
    return round(matched / len(stored_cols), 3)
