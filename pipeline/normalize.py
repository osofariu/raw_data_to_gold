"""
Normalization functions for cleaning raw data fields.

These functions are designed to be registered as SQLite user-defined functions
so they can be used directly in SQL views.
"""

import re


def normalize_machine_ref(raw: str | None) -> str | None:
    """
    Normalize a raw machine reference to canonical format (M-XXX).

    Args:
        raw: The raw machine reference string from incident_reports_raw

    Returns:
        Canonical machine code (e.g., 'M-017') or None if unmatchable

    Examples:
        >>> normalize_machine_ref('M-017')
        'M-017'
        >>> normalize_machine_ref('m-017')
        'M-017'
        >>> normalize_machine_ref('M017')
        'M-017'
        >>> normalize_machine_ref('017')
        'M-017'
        >>> normalize_machine_ref('Machine 17')
        'M-017'
        >>> normalize_machine_ref(' M-017 ')
        'M-017'
        >>> normalize_machine_ref('')
        >>> normalize_machine_ref(None)
    """
    if raw is None:
        return None

    # Clean whitespace
    cleaned = raw.strip()

    # Handle empty/placeholder values
    if cleaned == "" or cleaned.lower() in ("n/a", "unknown"):
        return None

    # Try to extract a 1-3 digit number
    match = re.search(r"(\d{1,3})", cleaned)
    if match:
        num = int(match.group(1))
        # Valid machine numbers are 1-40
        if 1 <= num <= 40:
            return f"M-{num:03d}"

    return None


def normalize_shift_code(raw: str | None) -> str | None:
    """
    Normalize a raw shift code reference to canonical format (S-YYYYMMDD-{D|S|N}).

    Args:
        raw: The raw shift_code_ref_raw string from incident_reports_raw

    Returns:
        Canonical shift code (e.g., 'S-20240115-D') or None if unmatchable

    Examples:
        >>> normalize_shift_code('S-20240115-D')
        'S-20240115-D'
        >>> normalize_shift_code('s-20240115-d')
        'S-20240115-D'
        >>> normalize_shift_code(' S-20240115-N ')
        'S-20240115-N'
        >>> normalize_shift_code('')
        >>> normalize_shift_code('n/a')
        >>> normalize_shift_code(None)
    """
    if raw is None:
        return None

    # Clean whitespace and uppercase
    cleaned = raw.strip().upper()

    # Handle empty/placeholder values
    if cleaned == "" or cleaned in ("N/A", "UNKNOWN", "NULL"):
        return None

    # Validate format: S-YYYYMMDD-{D|S|N}
    # Pattern: S- followed by 8 digits, hyphen, then D/S/N
    match = re.match(r"^S-(\d{8})-([DSN])$", cleaned)
    if match:
        return cleaned

    return None


def create_employee_normalizer(
    employees: list[tuple[int, str, str, str]],
):
    """
    Create an employee reference normalizer with lookup data.

    Since employee normalization requires lookups (name matching, ID validation),
    we create a closure that captures the lookup data built from the employees list.

    Args:
        employees: List of (employee_id, badge_id, first_name, last_name) tuples

    Returns:
        A normalize_employee_ref function suitable for SQLite UDF registration
    """
    # Build lookup structures
    badge_ids: set[str] = set()
    id_to_badge: dict[int, str] = {}
    name_to_badge: dict[str, str] = {}

    for emp_id, badge_id, first_name, last_name in employees:
        badge_ids.add(badge_id)
        id_to_badge[emp_id] = badge_id
        full_name = f"{first_name} {last_name}".upper()
        name_to_badge[full_name] = badge_id

    def normalize_employee_ref(raw: str | None) -> str | None:
        """
        Normalize a raw employee reference to canonical badge_id format (BXXXX).

        Handles multiple patterns:
        - Badge ID: B0042, b0042, Badge:B0042, ' B0042 '
        - EMP format: EMP-42, EMP42
        - Just number: 42 (as employee_id)
        - Full name: Casey Patel, CASEY PATEL

        Returns:
            Canonical badge_id (e.g., 'B0042') or None if unmatchable
        """
        if raw is None:
            return None

        # Clean whitespace
        cleaned = raw.strip()

        # Handle empty/placeholder values
        if cleaned == "" or cleaned.upper() in ("N/A", "UNKNOWN", "NULL", ""):
            return None

        # Strategy 1: Badge pattern (B0042, b0042, Badge:B0042)
        badge_match = re.search(r"B(\d{4})", cleaned, re.IGNORECASE)
        if badge_match:
            badge_id = f"B{badge_match.group(1)}"
            if badge_id in badge_ids:
                return badge_id

        # Strategy 2: EMP-ID pattern (EMP-42, EMP42)
        emp_match = re.match(r"^EMP-?(\d+)$", cleaned, re.IGNORECASE)
        if emp_match:
            emp_id = int(emp_match.group(1))
            if emp_id in id_to_badge:
                return id_to_badge[emp_id]

        # Strategy 3: Bare number (could be employee_id)
        if cleaned.isdigit():
            emp_id = int(cleaned)
            if emp_id in id_to_badge:
                return id_to_badge[emp_id]

        # Strategy 4: Full name matching
        name_upper = cleaned.upper()
        if name_upper in name_to_badge:
            return name_to_badge[name_upper]

        return None

    return normalize_employee_ref


# Mapping of incident type variants to canonical types
INCIDENT_TYPE_PATTERNS: dict[str, list[str]] = {
    "machine_failure": [
        "machine_failure",
        "machine failure",
        "machine_fail",
        "mech_fail",
        "mechf_ail",
        "mach failure",
        "machinef ailure",
        "mahcine failure",
    ],
    "safety_violation": [
        "safety_violation",
        "safety violation",
        "safety_viol",
        "safety-violation",
        "safety vio.",
    ],
    "near_miss": [
        "near_miss",
        "near miss",
        "near-miss",
        "nearmiss",
    ],
    "injury_minor": [
        "injury_minor",
        "minor injury",
        "min_inj",
        "minor inj.",
    ],
    "injury_major": [
        "injury_major",
        "major injury",
        "maj_inj",
        "major inj.",
    ],
    "quality_defect": [
        "quality_defect",
        "quality defect",
        "qa_defect",
        "quality issue",
    ],
    "power_event": [
        "power_event",
        "power event",
        "pwr_evt",
        "power fluctuation",
    ],
    "unknown": [
        "unknown",
        "unk",
        "?",
        "n/a",
    ],
}

# Build reverse lookup: variant -> canonical
_INCIDENT_TYPE_LOOKUP: dict[str, str] = {}
for canonical, variants in INCIDENT_TYPE_PATTERNS.items():
    for variant in variants:
        _INCIDENT_TYPE_LOOKUP[variant.lower()] = canonical


def normalize_incident_type(raw: str | None) -> str | None:
    """
    Normalize a raw incident type to canonical format.

    Args:
        raw: The raw incident_type_raw string from incident_reports_raw

    Returns:
        Canonical incident type (e.g., 'machine_failure') or None if unmatchable

    Examples:
        >>> normalize_incident_type('Machine Failure')
        'machine_failure'
        >>> normalize_incident_type('MECH_FAIL')
        'machine_failure'
        >>> normalize_incident_type('Near Miss')
        'near_miss'
        >>> normalize_incident_type('')
        >>> normalize_incident_type(None)
    """
    if raw is None:
        return None

    # Clean whitespace and lowercase
    cleaned = raw.strip().lower()

    # Handle empty values
    if cleaned == "":
        return None

    # Direct lookup
    if cleaned in _INCIDENT_TYPE_LOOKUP:
        return _INCIDENT_TYPE_LOOKUP[cleaned]

    # Try removing extra spaces and special chars for typo handling
    normalized = re.sub(r"[^a-z]", "", cleaned)
    for canonical, variants in INCIDENT_TYPE_PATTERNS.items():
        for variant in variants:
            variant_normalized = re.sub(r"[^a-z]", "", variant.lower())
            if normalized == variant_normalized:
                return canonical

    return None


# Month name to number mapping
_MONTH_MAP = {
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}


def parse_incident_time(raw: str | None) -> str | None:
    """
    Parse a raw incident time string to ISO format (YYYY-MM-DD HH:MM:SS).

    Handles multiple input formats:
    - ISO: 2024-07-05, 2024-07-30 16:17, 2024-08-02 17
    - DD-Mon-YYYY: 30-Aug-2025 05:19:00, 17-Jun-2024 05:44
    - MM/DD/YYYY: 05/23/2024, 06/23/2024 01:56:29

    Args:
        raw: The raw incident_time_raw string

    Returns:
        ISO formatted datetime (YYYY-MM-DD HH:MM:SS) or None if unparseable

    Examples:
        >>> parse_incident_time('2024-07-05')
        '2024-07-05 00:00:00'
        >>> parse_incident_time('30-Aug-2025 05:19:00')
        '2025-08-30 05:19:00'
        >>> parse_incident_time('05/23/2024')
        '2024-05-23 00:00:00'
    """
    if raw is None:
        return None

    # Clean whitespace
    cleaned = raw.strip()
    if cleaned == "":
        return None

    # Try to parse different formats
    date_part = None
    time_part = "00:00:00"

    # Split into date and time components
    parts = cleaned.split()
    date_str = parts[0]
    time_str = parts[1] if len(parts) > 1 else None

    # Format 1: ISO format (YYYY-MM-DD)
    iso_match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", date_str)
    if iso_match:
        date_part = date_str

    # Format 2: DD-Mon-YYYY (30-Aug-2025)
    if date_part is None:
        dmy_match = re.match(r"^(\d{1,2})-([A-Za-z]{3})-(\d{4})$", date_str)
        if dmy_match:
            day, mon, year = dmy_match.groups()
            mon_num = _MONTH_MAP.get(mon.lower())
            if mon_num:
                date_part = f"{year}-{mon_num}-{int(day):02d}"

    # Format 3: MM/DD/YYYY (05/23/2024)
    if date_part is None:
        mdy_match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", date_str)
        if mdy_match:
            mon, day, year = mdy_match.groups()
            date_part = f"{year}-{int(mon):02d}-{int(day):02d}"

    # If we couldn't parse the date, give up
    if date_part is None:
        return None

    # Parse time component if present
    if time_str:
        # Full time: HH:MM:SS
        if re.match(r"^\d{1,2}:\d{2}:\d{2}$", time_str):
            h, m, s = time_str.split(":")
            time_part = f"{int(h):02d}:{int(m):02d}:{int(s):02d}"
        # Partial time: HH:MM
        elif re.match(r"^\d{1,2}:\d{2}$", time_str):
            h, m = time_str.split(":")
            time_part = f"{int(h):02d}:{int(m):02d}:00"
        # Just hour: HH
        elif re.match(r"^\d{1,2}$", time_str):
            h = int(time_str)
            time_part = f"{h:02d}:00:00"

    return f"{date_part} {time_part}"
