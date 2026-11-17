"""Tests for Excel corruption fingerprint scanner."""
import pytest
from mapper.sanitize.fingerprint import scan_file


def test_clean_file_no_signals(clean_csv):
    result = scan_file(clean_csv)
    assert result["severity"] == "none"
    assert result["signals"] == []


def test_corrupted_file_detects_bom(corrupted_csv):
    result = scan_file(corrupted_csv)
    assert "bom" in result["signals"]


def test_corrupted_file_detects_crlf(corrupted_csv):
    result = scan_file(corrupted_csv)
    assert "crlf" in result["signals"]


def test_corrupted_file_detects_scientific_notation(corrupted_csv):
    result = scan_file(corrupted_csv)
    assert "scientific_notation" in result["signals"]


def test_corrupted_file_severity_is_critical(corrupted_csv):
    result = scan_file(corrupted_csv)
    assert result["severity"] == "critical"


def test_german_csv_no_corruption(german_csv):
    result = scan_file(german_csv)
    assert result["severity"] == "none"
