"""End-to-end pipeline tests."""
import pytest
from mapper.pipeline import process


class TestPipelineCleanEnglish:
    def test_returns_mapping_result(self, clean_csv, schema):
        result = process(clean_csv, schema)
        assert result is not None

    def test_no_corruption_on_clean_file(self, clean_csv, schema):
        result = process(clean_csv, schema)
        assert result.corruption_scan.severity == "none"

    def test_all_rows_extracted(self, clean_csv, schema):
        result = process(clean_csv, schema)
        assert result.summary.total_rows == 5

    def test_item_code_mapped(self, clean_csv, schema):
        result = process(clean_csv, schema)
        mapped_targets = {m.target_field for m in result.column_mapping.mapped}
        assert "item_code" in mapped_targets

    def test_rows_contain_item_code(self, clean_csv, schema):
        result = process(clean_csv, schema)
        for row in result.rows:
            assert "item_code" in row.mapped

    def test_quantities_are_floats(self, clean_csv, schema):
        result = process(clean_csv, schema)
        for row in result.rows:
            if "qty_shipped" in row.mapped:
                assert isinstance(row.mapped["qty_shipped"], float)

    def test_target_schema_echoed_back(self, clean_csv, schema):
        result = process(clean_csv, schema)
        assert result.target_schema is not None
        assert len(result.target_schema.fields) == len(schema.fields)


class TestPipelineGermanSupplier:
    def test_maps_german_headers(self, german_csv, schema):
        result = process(german_csv, schema)
        mapped_targets = {m.target_field for m in result.column_mapping.mapped}
        assert "item_code" in mapped_targets
        assert "unit_price" in mapped_targets

    def test_all_rows_extracted(self, german_csv, schema):
        result = process(german_csv, schema)
        assert result.summary.total_rows == 5

    def test_no_corruption(self, german_csv, schema):
        result = process(german_csv, schema)
        assert result.corruption_scan.severity == "none"


class TestPipelineExcelCorrupted:
    def test_detects_corruption(self, corrupted_csv, schema):
        result = process(corrupted_csv, schema)
        assert result.corruption_scan.severity in ("warn", "critical")

    def test_bom_signal_present(self, corrupted_csv, schema):
        result = process(corrupted_csv, schema)
        assert "bom" in result.corruption_scan.signals

    def test_scientific_notation_signal_present(self, corrupted_csv, schema):
        result = process(corrupted_csv, schema)
        assert "scientific_notation" in result.corruption_scan.signals

    def test_still_extracts_rows(self, corrupted_csv, schema):
        result = process(corrupted_csv, schema)
        assert result.summary.total_rows > 0


class TestPipelineRecordLinkage:
    def test_exact_match_via_key_xref(self, german_csv, schema, sample_records, sku_xref):
        result = process(
            german_csv, schema,
            records=sample_records,
            exact_keys=["item_code"],
            key_xref=sku_xref,
        )
        # German file uses supplier SKUs (SUP-xxx) — xref maps them to OUR-xxx
        assert result.summary.matched_to_record > 0

    def test_exact_match_on_clean_file(self, clean_csv, schema, sample_records):
        result = process(
            clean_csv, schema,
            records=sample_records,
            exact_keys=["item_code"],
        )
        # Clean file has OUR-xxx codes which match records directly
        assert result.summary.matched_to_record == result.summary.total_rows

    def test_unmatched_rows_go_to_review(self, clean_csv, schema):
        # Pass records that don't match any item_code
        mismatched_records = [{"id": "x", "item_code": "DOES-NOT-EXIST"}]
        result = process(
            clean_csv, schema,
            records=mismatched_records,
            exact_keys=["item_code"],
        )
        assert result.summary.unmatched == result.summary.total_rows
        row_match_items = [r for r in result.review_queue if r.kind == "row_match"]
        assert len(row_match_items) > 0


class TestPipelinePartialShipment:
    def test_partial_shipment_rows_extracted(self, partial_csv, schema):
        result = process(partial_csv, schema)
        assert result.summary.total_rows == 4

    def test_zero_qty_row_still_mapped(self, partial_csv, schema):
        result = process(partial_csv, schema)
        # Row with qty_shipped=0 should still be present
        shipped_values = [row.mapped.get("qty_shipped") for row in result.rows]
        assert 0.0 in shipped_values


class TestPipelineSourceProfile:
    def test_saves_and_reuses_profile(self, clean_csv, schema, tmp_path, monkeypatch):
        import mapper.profiles.profile_store as ps
        # Redirect profile store to tmp dir
        monkeypatch.setattr(ps, "PROFILES_DIR", tmp_path)

        # First run — save profile
        result1 = process(clean_csv, schema, source_id="TEST_SUPPLIER", confirm_and_save_profile=True)
        assert (tmp_path / "TEST_SUPPLIER.json").exists()

        # Second run — profile should be loaded
        result2 = process(clean_csv, schema, source_id="TEST_SUPPLIER")
        assert result2.metadata.profile_used == "TEST_SUPPLIER"
        assert result2.metadata.profile_confidence >= 0.8
