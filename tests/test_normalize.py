"""
Tests for normalization functions.
"""

import pytest
from pipeline.normalize import (
    normalize_machine_ref,
    normalize_shift_code,
    create_employee_normalizer,
    normalize_incident_type,
)


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


class TestNormalizeEmployeeRef:
    """Tests for employee reference normalization."""

    # Sample employee data for testing
    @pytest.fixture
    def normalizer(self):
        """Create a normalizer with sample employee data."""
        employees = [
            (1, "B0001", "Taylor", "Nguyen"),
            (10, "B0010", "Casey", "Patel"),
            (17, "B0017", "Hayden", "Johnson"),
            (42, "B0042", "Casey", "White"),
            (54, "B0054", "Jordan", "Brown"),
        ]
        return create_employee_normalizer(employees)

    # Strategy 1: Badge ID patterns
    def test_badge_canonical(self, normalizer):
        assert normalizer("B0017") == "B0017"
        assert normalizer("B0042") == "B0042"

    def test_badge_lowercase(self, normalizer):
        assert normalizer("b0017") == "B0017"
        assert normalizer("b0054") == "B0054"

    def test_badge_with_spaces(self, normalizer):
        assert normalizer(" B0017 ") == "B0017"
        assert normalizer("  B0042  ") == "B0042"

    def test_badge_with_prefix(self, normalizer):
        assert normalizer("Badge:B0017") == "B0017"
        assert normalizer("Badge:B0042") == "B0042"

    # Strategy 2: EMP-ID patterns
    def test_emp_format_with_hyphen(self, normalizer):
        assert normalizer("EMP-17") == "B0017"
        assert normalizer("EMP-1") == "B0001"

    def test_emp_format_no_hyphen(self, normalizer):
        assert normalizer("EMP17") == "B0017"
        assert normalizer("EMP42") == "B0042"

    def test_emp_format_lowercase(self, normalizer):
        assert normalizer("emp-17") == "B0017"
        assert normalizer("emp42") == "B0042"

    # Strategy 3: Bare number (employee_id)
    def test_bare_number(self, normalizer):
        assert normalizer("17") == "B0017"
        assert normalizer("1") == "B0001"
        assert normalizer("42") == "B0042"

    # Strategy 4: Full name matching
    def test_full_name(self, normalizer):
        assert normalizer("Casey Patel") == "B0010"
        assert normalizer("Hayden Johnson") == "B0017"

    def test_full_name_uppercase(self, normalizer):
        assert normalizer("CASEY PATEL") == "B0010"
        assert normalizer("HAYDEN JOHNSON") == "B0017"

    def test_full_name_lowercase(self, normalizer):
        assert normalizer("casey patel") == "B0010"
        assert normalizer("hayden johnson") == "B0017"

    # Empty/placeholder values
    def test_empty_values(self, normalizer):
        assert normalizer(None) is None
        assert normalizer("") is None
        assert normalizer("   ") is None

    def test_placeholder_values(self, normalizer):
        assert normalizer("n/a") is None
        assert normalizer("N/A") is None
        assert normalizer("UNKNOWN") is None
        assert normalizer("unknown") is None

    # Invalid/non-existent references
    def test_invalid_badge(self, normalizer):
        assert normalizer("B9999") is None  # Doesn't exist
        assert normalizer("B0099") is None  # Doesn't exist

    def test_invalid_emp_id(self, normalizer):
        assert normalizer("EMP-999") is None  # Doesn't exist
        assert normalizer("999") is None  # Doesn't exist

    def test_invalid_name(self, normalizer):
        assert normalizer("John Doe") is None  # Doesn't exist
        assert normalizer("NOBODY HERE") is None


class TestNormalizeIncidentType:
    """Tests for normalize_incident_type function."""

    # Machine failure variants
    def test_machine_failure(self):
        assert normalize_incident_type("machine_failure") == "machine_failure"
        assert normalize_incident_type("Machine Failure") == "machine_failure"
        assert normalize_incident_type("MECH_FAIL") == "machine_failure"
        assert normalize_incident_type("machine_fail") == "machine_failure"
        assert normalize_incident_type("Mach failure") == "machine_failure"
        assert normalize_incident_type("machine failure ") == "machine_failure"

    def test_machine_failure_typos(self):
        assert normalize_incident_type("Mahcine Failure") == "machine_failure"
        assert normalize_incident_type("MachineF ailure") == "machine_failure"
        assert normalize_incident_type("MECHF_AIL") == "machine_failure"

    # Safety violation variants
    def test_safety_violation(self):
        assert normalize_incident_type("safety_violation") == "safety_violation"
        assert normalize_incident_type("Safety Violation") == "safety_violation"
        assert normalize_incident_type("SAFETY_VIOL") == "safety_violation"
        assert normalize_incident_type("safety-violation") == "safety_violation"
        assert normalize_incident_type("Safety vio.") == "safety_violation"

    # Near miss variants
    def test_near_miss(self):
        assert normalize_incident_type("near_miss") == "near_miss"
        assert normalize_incident_type("Near Miss") == "near_miss"
        assert normalize_incident_type("NEAR_MISS") == "near_miss"
        assert normalize_incident_type("near-miss") == "near_miss"
        assert normalize_incident_type("Nearmiss") == "near_miss"

    # Injury variants
    def test_injury_minor(self):
        assert normalize_incident_type("injury_minor") == "injury_minor"
        assert normalize_incident_type("Minor Injury") == "injury_minor"
        assert normalize_incident_type("MIN_INJ") == "injury_minor"
        assert normalize_incident_type("Minor inj.") == "injury_minor"

    def test_injury_major(self):
        assert normalize_incident_type("injury_major") == "injury_major"
        assert normalize_incident_type("Major Injury") == "injury_major"

    # Quality defect variants
    def test_quality_defect(self):
        assert normalize_incident_type("quality_defect") == "quality_defect"
        assert normalize_incident_type("Quality Defect") == "quality_defect"
        assert normalize_incident_type("QA_DEFECT") == "quality_defect"
        assert normalize_incident_type("Quality issue") == "quality_defect"

    # Power event variants
    def test_power_event(self):
        assert normalize_incident_type("power_event") == "power_event"
        assert normalize_incident_type("Power Event") == "power_event"
        assert normalize_incident_type("PWR_EVT") == "power_event"
        assert normalize_incident_type("Power fluctuation") == "power_event"

    # Empty/placeholder values
    def test_empty_values(self):
        assert normalize_incident_type(None) is None
        assert normalize_incident_type("") is None
        assert normalize_incident_type("   ") is None

    # Unknown/unrecognized
    def test_unknown(self):
        assert normalize_incident_type("unknown") == "unknown"
        assert normalize_incident_type("UNK") == "unknown"
        assert normalize_incident_type("?") == "unknown"

    def test_unrecognized(self):
        assert normalize_incident_type("random garbage") is None
        assert normalize_incident_type("not a real type") is None
