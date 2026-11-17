"""Shared pytest fixtures."""
import json
from pathlib import Path
import pytest
from mapper.models import TargetSchema

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def schema() -> TargetSchema:
    data = json.loads((FIXTURES / "sample_schema.json").read_text())
    return TargetSchema.model_validate(data)


@pytest.fixture
def clean_csv(tmp_path) -> Path:
    return FIXTURES / "clean_english.csv"


@pytest.fixture
def german_csv() -> Path:
    return FIXTURES / "german_supplier.csv"


@pytest.fixture
def cryptic_csv() -> Path:
    return FIXTURES / "cryptic_headers.csv"


@pytest.fixture
def corrupted_csv() -> Path:
    return FIXTURES / "excel_corrupted.csv"


@pytest.fixture
def partial_csv() -> Path:
    return FIXTURES / "partial_shipment.csv"


@pytest.fixture
def sample_records() -> list[dict]:
    """Simulated target system records to match rows against."""
    return [
        {"id": "rec-001", "item_code": "OUR-456", "description": "Widget A Premium"},
        {"id": "rec-002", "item_code": "OUR-789", "description": "Widget B Standard"},
        {"id": "rec-003", "item_code": "OUR-321", "description": "Connector Type-C"},
        {"id": "rec-004", "item_code": "OUR-111", "description": "Mounting Bracket"},
        {"id": "rec-005", "item_code": "OUR-222", "description": "Cable Assembly"},
    ]


@pytest.fixture
def sku_xref() -> dict:
    """Supplier SKU → target record item_code cross-reference."""
    return {
        "SUP-123": "OUR-456",
        "SUP-999": "OUR-789",
        "SUP-456": "OUR-321",
        "SUP-777": "OUR-111",
        "SUP-888": "OUR-222",
    }
