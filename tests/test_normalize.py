"""
Tests for normalization functions.
"""

import pytest
from pipeline.normalize import (
    normalize_machine_ref,
    normalize_shift_code,
    create_employee_normalizer,
    normalize_incident_type,
    parse_incident_time,
    normalize_zone_ref,
    normalize_severity,
    parse_reported_time,
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


class TestParseIncidentTime:
    """Tests for parse_incident_time function."""

    # ISO format (YYYY-MM-DD)
    def test_iso_date_only(self):
        assert parse_incident_time("2024-07-05") == "2024-07-05 00:00:00"
        assert parse_incident_time("2025-11-15") == "2025-11-15 00:00:00"

    def test_iso_with_full_time(self):
        assert parse_incident_time("2024-07-30 16:17:00") == "2024-07-30 16:17:00"
        assert parse_incident_time("2024-01-15 09:05:30") == "2024-01-15 09:05:30"

    def test_iso_with_partial_time(self):
        assert parse_incident_time("2024-07-30 16:17") == "2024-07-30 16:17:00"
        assert parse_incident_time("2024-08-02 17") == "2024-08-02 17:00:00"

    # DD-Mon-YYYY format
    def test_dmy_date_only(self):
        assert parse_incident_time("30-Aug-2025") == "2025-08-30 00:00:00"
        assert parse_incident_time("1-Jan-2024") == "2024-01-01 00:00:00"

    def test_dmy_with_full_time(self):
        assert parse_incident_time("30-Aug-2025 05:19:00") == "2025-08-30 05:19:00"
        assert parse_incident_time("27-Mar-2024 17:48:53") == "2024-03-27 17:48:53"

    def test_dmy_with_partial_time(self):
        assert parse_incident_time("17-Jun-2024 05:44") == "2024-06-17 05:44:00"
        assert parse_incident_time("27-Apr-2025 16") == "2025-04-27 16:00:00"

    # MM/DD/YYYY format
    def test_mdy_date_only(self):
        assert parse_incident_time("05/23/2024") == "2024-05-23 00:00:00"
        assert parse_incident_time("12/25/2024") == "2024-12-25 00:00:00"

    def test_mdy_with_full_time(self):
        assert parse_incident_time("06/23/2024 01:56:29") == "2024-06-23 01:56:29"
        assert parse_incident_time("12/25/2024 14:47:11") == "2024-12-25 14:47:11"

    def test_mdy_with_partial_time(self):
        assert parse_incident_time("10/27/2024 22:35") == "2024-10-27 22:35:00"

    # Whitespace handling
    def test_whitespace(self):
        assert parse_incident_time(" 2024-07-05 ") == "2024-07-05 00:00:00"
        assert parse_incident_time(" 05/30/2024 02:20:08 ") == "2024-05-30 02:20:08"
        assert parse_incident_time(" 10-May-2025 19:15 ") == "2025-05-10 19:15:00"

    # Empty/null values
    def test_empty_values(self):
        assert parse_incident_time(None) is None
        assert parse_incident_time("") is None
        assert parse_incident_time("   ") is None

    # Invalid formats
    def test_invalid(self):
        assert parse_incident_time("not a date") is None
        assert parse_incident_time("2024/07/05") is None  # Wrong separator for ISO
        assert parse_incident_time("July 5, 2024") is None  # Unsupported format


class TestNormalizeZoneRef:
    """Tests for normalize_zone_ref function."""

    # Canonical format
    def test_canonical_format(self):
        assert normalize_zone_ref("Z-01") == "Z-01"
        assert normalize_zone_ref("Z-03") == "Z-03"
        assert normalize_zone_ref("Z-06") == "Z-06"

    # Case variations
    def test_lowercase(self):
        assert normalize_zone_ref("z-03") == "Z-03"
        assert normalize_zone_ref("z-01") == "Z-01"

    # No hyphen
    def test_no_hyphen(self):
        assert normalize_zone_ref("Z03") == "Z-03"
        assert normalize_zone_ref("z03") == "Z-03"
        assert normalize_zone_ref("Z1") == "Z-01"

    # Verbose format with "Zone" prefix
    def test_verbose_prefix(self):
        assert normalize_zone_ref("Zone Z-03") == "Z-03"
        assert normalize_zone_ref("ZONE Z-02") == "Z-02"
        assert normalize_zone_ref("Zone Z03") == "Z-03"

    # Whitespace
    def test_whitespace(self):
        assert normalize_zone_ref(" Z-03 ") == "Z-03"
        assert normalize_zone_ref("  Z03  ") == "Z-03"
        assert normalize_zone_ref("\tZ-01\n") == "Z-01"

    # All valid zones (1-6)
    def test_all_valid_zones(self):
        for i in range(1, 7):
            assert normalize_zone_ref(f"Z-0{i}") == f"Z-0{i}"
            assert normalize_zone_ref(f"Z{i}") == f"Z-0{i}"

    # Invalid zone numbers
    def test_invalid_zone_number(self):
        assert normalize_zone_ref("Z-00") is None
        assert normalize_zone_ref("Z-07") is None
        assert normalize_zone_ref("Z-99") is None
        assert normalize_zone_ref("Z-10") is None

    # Placeholder values
    def test_placeholder_values(self):
        assert normalize_zone_ref("ZONE-UNKNOWN") is None
        assert normalize_zone_ref("n/a") is None
        assert normalize_zone_ref("N/A") is None
        assert normalize_zone_ref("unknown") is None
        assert normalize_zone_ref("UNKNOWN") is None

    # Empty/null values
    def test_empty_values(self):
        assert normalize_zone_ref(None) is None
        assert normalize_zone_ref("") is None
        assert normalize_zone_ref("   ") is None


class TestNormalizeSeverity:
    """Tests for normalize_severity function."""

    # Canonical values
    def test_canonical_values(self):
        assert normalize_severity("low") == "low"
        assert normalize_severity("medium") == "medium"
        assert normalize_severity("high") == "high"
        assert normalize_severity("critical") == "critical"

    # Uppercase
    def test_uppercase(self):
        assert normalize_severity("LOW") == "low"
        assert normalize_severity("MED") == "medium"
        assert normalize_severity("HIGH") == "high"
        assert normalize_severity("CRITICAL") == "critical"

    # Numeric values
    def test_numeric_values(self):
        assert normalize_severity("1") == "low"
        assert normalize_severity("2") == "medium"
        assert normalize_severity("3") == "high"
        assert normalize_severity("4") == "critical"
        assert normalize_severity("5") == "critical"

    # sev pattern
    def test_sev_pattern(self):
        assert normalize_severity("sev1") == "low"
        assert normalize_severity("sev2") == "medium"
        assert normalize_severity("sev3") == "high"
        assert normalize_severity("sev4") == "critical"
        assert normalize_severity("SEV1") == "low"
        assert normalize_severity("SEV2") == "medium"

    # Word variants
    def test_word_variants(self):
        assert normalize_severity("minor") == "low"
        assert normalize_severity("moderate") == "medium"
        assert normalize_severity("major") == "high"
        assert normalize_severity("crit") == "critical"

    # Single letter
    def test_single_letter(self):
        assert normalize_severity("L") == "low"
        assert normalize_severity("M") == "medium"
        assert normalize_severity("H") == "high"
        assert normalize_severity("l") == "low"
        assert normalize_severity("m") == "medium"
        assert normalize_severity("h") == "high"

    # Typos
    def test_typos(self):
        assert normalize_severity("mdeium") == "medium"

    # Whitespace
    def test_whitespace(self):
        assert normalize_severity(" low ") == "low"
        assert normalize_severity("  HIGH  ") == "high"
        assert normalize_severity("\tmedium\n") == "medium"

    # Empty/null values
    def test_empty_values(self):
        assert normalize_severity(None) is None
        assert normalize_severity("") is None
        assert normalize_severity("   ") is None

    # Placeholder values
    def test_placeholder_values(self):
        assert normalize_severity("n/a") is None
        assert normalize_severity("N/A") is None
        assert normalize_severity("unknown") is None

    # Invalid/unrecognized
    def test_unrecognized(self):
        assert normalize_severity("garbage") is None
        assert normalize_severity("super high") is None


class TestParseReportedTime:
    """Tests for parse_reported_time function."""

    # ISO format
    def test_iso_date(self):
        assert parse_reported_time("2024-04-18") == "2024-04-18 00:00:00"
        assert parse_reported_time("2024-01-31") == "2024-01-31 00:00:00"

    # DD-Mon-YYYY format
    def test_dmy_full_time(self):
        assert parse_reported_time("31-May-2025 02:20:12") == "2025-05-31 02:20:12"
        assert parse_reported_time("30-Aug-2025 22:06:17") == "2025-08-30 22:06:17"

    def test_dmy_partial_time(self):
        assert parse_reported_time("29-Oct-2025 21:02") == "2025-10-29 21:02:00"
        assert parse_reported_time("29-May-2024 03:20") == "2024-05-29 03:20:00"

    def test_dmy_hour_only(self):
        assert parse_reported_time("29-Oct-2024 00") == "2024-10-29 00:00:00"
        assert parse_reported_time("29-Nov-2025 16") == "2025-11-29 16:00:00"

    def test_dmy_no_time(self):
        assert parse_reported_time("30-Jan-2024") == "2024-01-30 00:00:00"
        assert parse_reported_time("31-Mar-2025") == "2025-03-31 00:00:00"

    # MM/DD/YYYY format
    def test_mdy_format(self):
        assert parse_reported_time("12/10/2024") == "2024-12-10 00:00:00"
        assert parse_reported_time("05/23/2024") == "2024-05-23 00:00:00"

    # Whitespace
    def test_whitespace(self):
        assert parse_reported_time(" 2024-04-18 ") == "2024-04-18 00:00:00"
        assert parse_reported_time("  31-May-2025 02:20:12  ") == "2025-05-31 02:20:12"

    # Empty/null values
    def test_empty_values(self):
        assert parse_reported_time(None) is None
        assert parse_reported_time("") is None
        assert parse_reported_time("   ") is None

    # Invalid formats
    def test_invalid(self):
        assert parse_reported_time("not a date") is None
        assert parse_reported_time("garbage") is None
