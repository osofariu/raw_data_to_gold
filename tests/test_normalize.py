"""
Tests for normalization functions.
"""

import pytest
from pipeline.normalize import normalize_machine_ref, normalize_shift_code


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


class TestNormalizeShiftCode:
    """Tests for normalize_shift_code function."""

    # Canonical format
    def test_canonical_format(self):
        assert normalize_shift_code("S-20240115-D") == "S-20240115-D"
        assert normalize_shift_code("S-20240115-S") == "S-20240115-S"
        assert normalize_shift_code("S-20240115-N") == "S-20240115-N"

    # Case variations
    def test_lowercase(self):
        assert normalize_shift_code("s-20240115-d") == "S-20240115-D"
        assert normalize_shift_code("s-20240115-s") == "S-20240115-S"
        assert normalize_shift_code("s-20240115-n") == "S-20240115-N"

    # Whitespace
    def test_whitespace(self):
        assert normalize_shift_code(" S-20240115-D ") == "S-20240115-D"
        assert normalize_shift_code("  S-20240115-N  ") == "S-20240115-N"
        assert normalize_shift_code("\tS-20240115-S\n") == "S-20240115-S"

    # Empty/missing values
    def test_empty_values(self):
        assert normalize_shift_code(None) is None
        assert normalize_shift_code("") is None
        assert normalize_shift_code("   ") is None

    # Placeholder values
    def test_placeholder_values(self):
        assert normalize_shift_code("n/a") is None
        assert normalize_shift_code("N/A") is None
        assert normalize_shift_code("unknown") is None
        assert normalize_shift_code("UNKNOWN") is None
        assert normalize_shift_code("null") is None

    # Invalid formats
    def test_invalid_formats(self):
        # Missing parts
        assert normalize_shift_code("S-20240115") is None
        assert normalize_shift_code("20240115-D") is None
        # Wrong prefix
        assert normalize_shift_code("X-20240115-D") is None
        # Wrong shift type
        assert normalize_shift_code("S-20240115-X") is None
        # Wrong date length
        assert normalize_shift_code("S-2024011-D") is None
        assert normalize_shift_code("S-202401155-D") is None

    # Mixed case
    def test_mixed_case(self):
        assert normalize_shift_code("S-20240115-d") == "S-20240115-D"
        assert normalize_shift_code("s-20240115-D") == "S-20240115-D"
