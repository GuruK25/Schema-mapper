"""Tests for column mapping — linguistic matcher, domain classifier, hybrid scorer."""
import pytest
from mapper.matching.linguistic_matcher import score_column, rank_targets
from mapper.matching.domain_classifier import classify_column
from mapper.matching.hybrid_scorer import map_columns


# ---------------------------------------------------------------------------
# Linguistic matcher
# ---------------------------------------------------------------------------

class TestLinguisticMatcher:
    def test_exact_synonym_scores_high(self, schema):
        # "unit price" is a synonym of unit_price field
        score = score_column("Unit Price", "unit_price", schema)
        assert score >= 0.9

    def test_german_header_scores_high(self, schema):
        # "Stk-Preis" is a synonym of unit_price
        score = score_column("Stk-Preis", "unit_price", schema)
        assert score >= 0.8

    def test_wrong_field_scores_low(self, schema):
        score = score_column("Unit Price", "lot_number", schema)
        assert score < 0.5

    def test_rank_returns_all_fields(self, schema):
        ranked = rank_targets("Quantity", schema)
        field_names = [name for name, _ in ranked]
        assert set(field_names) == {f.name for f in schema.fields}

    def test_rank_top_result_is_best_match(self, schema):
        ranked = rank_targets("Ship Qty", schema)
        assert ranked[0][0] in ("qty_shipped", "qty_ordered")

    def test_abbreviated_header_still_matches(self, schema):
        # "Shp" is in the synonyms list for qty_shipped
        score = score_column("Shp", "qty_shipped", schema)
        assert score > 0.0


# ---------------------------------------------------------------------------
# Domain classifier
# ---------------------------------------------------------------------------

class TestDomainClassifier:
    def test_classifies_skus(self):
        values = ["OUR-456", "OUR-789", "OUR-321", "OUR-111", "OUR-222"]
        domain, conf = classify_column(values)
        assert domain == "sku"
        assert conf >= 0.8

    def test_classifies_quantities(self):
        values = ["100", "50", "200", "75", "30"]
        domain, conf = classify_column(values)
        assert domain == "qty"
        assert conf > 0.5

    def test_classifies_prices(self):
        values = ["12.50", "8.75", "3.20", "5.00", "22.00"]
        domain, conf = classify_column(values)
        assert domain in ("unit_price", "qty")

    def test_classifies_dates(self):
        values = ["2024-11-15", "2024-11-15", "2024-11-15", "2024-11-16", "2024-11-16"]
        domain, conf = classify_column(values)
        assert domain == "date"
        assert conf >= 0.9

    def test_classifies_descriptions(self):
        values = ["Widget A Premium", "Widget B Standard", "Connector Type-C", "Mounting Bracket"]
        domain, conf = classify_column(values)
        assert domain == "description"

    def test_empty_column_returns_unknown(self):
        domain, conf = classify_column(["", "", ""])
        assert domain == "unknown"
        assert conf == 0.0


# ---------------------------------------------------------------------------
# Hybrid scorer
# ---------------------------------------------------------------------------

class TestHybridScorer:
    def test_maps_english_headers(self, schema):
        headers = ["Part Number", "Description", "Order Qty", "Ship Qty", "Unit Price", "Total", "Ship Date", "Lot"]
        rows = [
            {"Part Number": "OUR-456", "Description": "Widget A", "Order Qty": "100",
             "Ship Qty": "100", "Unit Price": "12.50", "Total": "1250.00",
             "Ship Date": "2024-11-15", "Lot": "LOT-001"}
        ]
        result = map_columns(headers, rows, schema)
        mapped_targets = {m.target_field for m in result.mapped}
        assert "item_code" in mapped_targets
        assert "qty_shipped" in mapped_targets
        assert "unit_price" in mapped_targets

    def test_maps_german_headers(self, schema):
        headers = ["Art. Nr.", "Bezeichnung", "Menge bestellt", "Menge geliefert", "Stk-Preis", "Gesamt", "Lieferdatum", "Charge"]
        rows = [
            {"Art. Nr.": "SUP-123", "Bezeichnung": "Widget A", "Menge bestellt": "100",
             "Menge geliefert": "100", "Stk-Preis": "12.50", "Gesamt": "1250.00",
             "Lieferdatum": "15.11.2024", "Charge": "L-001"}
        ]
        result = map_columns(headers, rows, schema)
        mapped_targets = {m.target_field for m in result.mapped}
        assert "item_code" in mapped_targets
        assert "unit_price" in mapped_targets

    def test_confidence_above_threshold(self, schema):
        headers = ["Part Number", "Ship Qty", "Unit Price"]
        rows = [{"Part Number": "OUR-456", "Ship Qty": "100", "Unit Price": "12.50"}]
        result = map_columns(headers, rows, schema)
        for m in result.mapped:
            assert m.confidence >= 0.40  # at least above REVIEW_THRESHOLD

    def test_unrecognised_column_goes_to_unmapped(self, schema):
        headers = ["Part Number", "XYZZY_COLUMN"]
        rows = [{"Part Number": "OUR-456", "XYZZY_COLUMN": "???"}]
        result = map_columns(headers, rows, schema)
        assert "XYZZY_COLUMN" in result.unmapped_supplier_columns
