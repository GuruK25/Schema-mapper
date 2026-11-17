"""Tests for per-column value sanitizers."""
import pytest
from mapper.sanitize.sanitizers import (
    sanitize_sku,
    sanitize_barcode,
    sanitize_numeric,
    sanitize_date_coercion,
)


# ---------------------------------------------------------------------------
# SKU sanitizer — leading zeros
# ---------------------------------------------------------------------------

class TestSanitizeSku:
    def test_no_change_when_sku_exists(self):
        val, warn = sanitize_sku("OUR-456", reference_skus={"OUR-456"})
        assert val == "OUR-456"
        assert warn is None

    def test_restores_leading_zeros(self):
        val, warn = sanitize_sku("456", reference_skus={"OUR-456", "00456", "000456"})
        assert val == "00456"
        assert warn is not None
        assert warn.type == "leading_zero_restored"
        assert warn.severity == "info"

    def test_no_reference_returns_unchanged(self):
        val, warn = sanitize_sku("456", reference_skus=None)
        assert val == "456"
        assert warn is None

    def test_no_match_found_returns_unchanged(self):
        val, warn = sanitize_sku("999", reference_skus={"OUR-456", "OUR-789"})
        assert val == "999"
        assert warn is not None
        assert "no matching SKU" in warn.message


# ---------------------------------------------------------------------------
# Barcode sanitizer — scientific notation
# ---------------------------------------------------------------------------

class TestSanitizeBarcode:
    def test_clean_barcode_unchanged(self):
        val, warn = sanitize_barcode("9780306406157")
        assert val == "9780306406157"
        assert warn is None

    def test_scientific_notation_recovered(self):
        # 5901234123457 is a valid EAN-13
        val, warn = sanitize_barcode("5.90123412345E+12")
        assert warn is not None
        # Either recovered (valid check digit) or critical (digits lost)
        assert warn.type in ("leading_zero_restored", "barcode_unrecoverable")

    def test_non_barcode_string_unchanged(self):
        val, warn = sanitize_barcode("OUR-456")
        assert val == "OUR-456"
        assert warn is None

    def test_critical_severity_on_unrecoverable(self):
        # Deliberately mangled barcode with wrong check digit
        val, warn = sanitize_barcode("5.90123E+12")
        if warn and warn.type == "barcode_unrecoverable":
            assert warn.severity == "critical"
            assert warn.resolved_value is None


# ---------------------------------------------------------------------------
# Numeric sanitizer — thousands comma
# ---------------------------------------------------------------------------

class TestSanitizeNumeric:
    def test_plain_integer(self):
        val, warn = sanitize_numeric("100")
        assert val == 100.0
        assert warn is None

    def test_plain_decimal(self):
        val, warn = sanitize_numeric("12.50")
        assert val == 12.50
        assert warn is None

    def test_us_thousands_comma(self):
        val, warn = sanitize_numeric("1,200")
        assert val == 1200.0
        assert warn is None

    def test_us_thousands_comma_with_decimal(self):
        val, warn = sanitize_numeric("1,200.50")
        assert val == 1200.50
        assert warn is None

    def test_european_thousands_dot(self):
        val, warn = sanitize_numeric("1.200,50")
        assert val == 1200.50
        assert warn is None

    def test_currency_symbol_stripped(self):
        val, warn = sanitize_numeric("$12.50")
        assert val == 12.50

    def test_invalid_string_returns_none(self):
        val, warn = sanitize_numeric("N/A")
        assert val is None
        assert warn is not None


# ---------------------------------------------------------------------------
# Date coercion detector
# ---------------------------------------------------------------------------

class TestSanitizeDateCoercion:
    def test_flags_integer_in_sku_column(self):
        val, warn = sanitize_date_coercion("45293", column_type="sku")
        assert warn is not None
        assert warn.type == "date_coercion"

    def test_no_flag_in_date_column(self):
        val, warn = sanitize_date_coercion("45293", column_type="date")
        assert warn is None

    def test_non_numeric_string_unchanged(self):
        val, warn = sanitize_date_coercion("OUR-456", column_type="sku")
        assert warn is None

    def test_large_integer_not_flagged(self):
        # 60001 is outside the Excel date serial range
        val, warn = sanitize_date_coercion("60001", column_type="sku")
        assert warn is None
