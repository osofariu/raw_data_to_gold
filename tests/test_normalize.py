"""
Tests for normalization functions.
"""

import pytest
from pipeline.normalize import normalize_machine_ref


class TestNormalizeMachineRef:
    """Tests for normalize_machine_ref function."""

    # Canonical format
    def test_canonical_format(self):
        assert normalize_machine_ref("M-017") == "M-017"
        assert normalize_machine_ref("M-003") == "M-003"
        assert normalize_machine_ref("M-040") == "M-040"

    # Case variations
    def test_lowercase(self):
        assert normalize_machine_ref("m-017") == "M-017"
        assert normalize_machine_ref("m-003") == "M-003"

    # No hyphen
    def test_no_hyphen(self):
        assert normalize_machine_ref("M017") == "M-017"
        assert normalize_machine_ref("m017") == "M-017"
        assert normalize_machine_ref("M003") == "M-003"

    # Just digits
    def test_digits_only(self):
        assert normalize_machine_ref("017") == "M-017"
        assert normalize_machine_ref("17") == "M-017"
        assert normalize_machine_ref("3") == "M-003"

    # Verbose format
    def test_verbose_format(self):
        assert normalize_machine_ref("Machine 017") == "M-017"
        assert normalize_machine_ref("Machine 17") == "M-017"
        assert normalize_machine_ref("Machine 3") == "M-003"

    # Whitespace
    def test_whitespace(self):
        assert normalize_machine_ref(" M-017 ") == "M-017"
        assert normalize_machine_ref("  M017  ") == "M-017"
        assert normalize_machine_ref("\tM-017\n") == "M-017"

    # Typos (wrong prefix but extractable number)
    def test_typos(self):
        assert normalize_machine_ref("MX-017") == "M-017"
        assert normalize_machine_ref("MX017") == "M-017"

    # Empty/missing values
    def test_empty_values(self):
        assert normalize_machine_ref(None) is None
        assert normalize_machine_ref("") is None
        assert normalize_machine_ref("   ") is None

    # Placeholder values
    def test_placeholder_values(self):
        assert normalize_machine_ref("n/a") is None
        assert normalize_machine_ref("N/A") is None
        assert normalize_machine_ref("unknown") is None
        assert normalize_machine_ref("UNKNOWN") is None

    # Out of range (machines are 1-40)
    def test_out_of_range(self):
        assert normalize_machine_ref("M-000") is None
        assert normalize_machine_ref("M-041") is None
        assert normalize_machine_ref("M-404") is None
        assert normalize_machine_ref("MX-404") is None

    # Edge cases
    def test_edge_cases(self):
        # Minimum valid
        assert normalize_machine_ref("M-001") == "M-001"
        assert normalize_machine_ref("1") == "M-001"
        # Maximum valid
        assert normalize_machine_ref("M-040") == "M-040"
        assert normalize_machine_ref("40") == "M-040"
