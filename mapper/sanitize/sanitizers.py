"""Per-column value sanitizers. Each returns (clean_value, warning | None)."""
from __future__ import annotations
import re
from mapper.models import Warning


EXCEL_DATE_SERIAL_RANGE = range(1, 60000)
SCIENTIFIC = re.compile(r"^(\d+)\.(\d+)[Ee]\+?(\d+)$")
THOUSANDS_US = re.compile(r"^\d{1,3}(,\d{3})*(\.\d+)?$")
THOUSANDS_EU = re.compile(r"^\d{1,3}(\.\d{3})*(,\d+)?$")


def sanitize_sku(value: str, reference_skus: set[str] | None = None) -> tuple[str, Warning | None]:
    val = value.strip()
    if not val:
        return val, None

    if reference_skus and val in reference_skus:
        return val, None

    if reference_skus:
        for length in range(len(val) + 1, 15):
            padded = val.zfill(length)
            if padded in reference_skus:
                return padded, Warning(
                    severity="info",
                    type="leading_zero_restored",
                    field="sku",
                    original_value=val,
                    resolved_value=padded,
                    message=f"Leading zeros restored: {val} → {padded}",
                )

    return val, None


def sanitize_barcode(value: str) -> tuple[str, Warning | None]:
    val = value.strip()
    m = SCIENTIFIC.match(val)
    if not m:
        return val, None

    # Reconstruct integer from scientific notation
    reconstructed = str(int(float(val)))

    if _valid_ean_check_digit(reconstructed):
        return reconstructed, Warning(
            severity="warn",
            type="leading_zero_restored",
            field="barcode",
            original_value=val,
            resolved_value=reconstructed,
            message=f"Scientific notation converted: {val} → {reconstructed}",
        )

    return reconstructed, Warning(
        severity="critical",
        type="barcode_unrecoverable",
        field="barcode",
        original_value=val,
        resolved_value=None,
        message=f"Barcode precision lost due to Excel scientific notation: {val}",
    )


def sanitize_numeric(value: str) -> tuple[float | None, Warning | None]:
    val = value.strip().lstrip("$€£")

    if THOUSANDS_EU.match(val) and "," in val:
        cleaned = val.replace(".", "").replace(",", ".")
    elif THOUSANDS_US.match(val) and "," in val:
        cleaned = val.replace(",", "")
    else:
        cleaned = val

    try:
        return float(cleaned), None
    except ValueError:
        return None, Warning(
            severity="warn",
            type="thousands_comma",
            field="numeric",
            original_value=value,
            resolved_value=None,
            message=f"Could not parse numeric value: {value!r}",
        )


def sanitize_date_coercion(value: str, column_type: str = "sku") -> tuple[str, Warning | None]:
    """Flag integers that might be Excel date serials in non-date columns."""
    try:
        int_val = int(value.strip())
    except ValueError:
        return value, None

    if column_type != "date" and int_val in EXCEL_DATE_SERIAL_RANGE:
        return value, Warning(
            severity="warn",
            type="date_coercion",
            field=column_type,
            original_value=value,
            resolved_value=None,
            message=f"Value {value!r} may be an Excel date serial in a non-date column",
        )
    return value, None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_ean_check_digit(barcode: str) -> bool:
    if len(barcode) not in (8, 12, 13, 14):
        return False
    digits = [int(d) for d in barcode]
    total = sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits[:-1]))
    expected = (10 - (total % 10)) % 10
    return expected == digits[-1]
