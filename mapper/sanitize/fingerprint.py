"""Detect signs that a file was opened and re-saved by Excel."""
from pathlib import Path
import re


SIGNALS = {
    "bom":             lambda raw, _: raw.startswith(b"\xef\xbb\xbf"),
    "crlf":            lambda raw, _: b"\r\n" in raw,
    "scientific_notation": lambda _, text: bool(re.search(r"\d+\.\d+[Ee][+\-]?\d+", text)),
    "thousands_comma": lambda _, text: bool(re.search(r'"\d{1,3}(,\d{3})+"', text)),
    "date_in_id_col":  lambda _, text: bool(re.search(r"\b\d{1,2}/\d{1,2}/\d{4}\b", text)),
}

SEVERITY_MAP = {
    0: "none",
    1: "warn",
    2: "warn",
}


def scan_file(path: str | Path) -> dict:
    """
    Returns {severity, signals, details}.
    Call this immediately after raw ingest, before any mapping.
    """
    raw = Path(path).read_bytes()
    text = raw.decode("utf-8", errors="replace")

    triggered = [name for name, fn in SIGNALS.items() if fn(raw, text)]
    critical = "scientific_notation" in triggered

    return {
        "severity": "critical" if critical else ("warn" if triggered else "none"),
        "signals": triggered,
        "details": [],   # populated by per-column sanitizers after column classification
    }
