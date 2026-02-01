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
    badge_ids: set[str],
    id_to_badge: dict[int, str],
    name_to_badge: dict[str, str],
):
    """
    Factory function that creates an employee reference normalizer.

    Since employee normalization requires lookups (name matching, ID validation),
    we create a closure that captures the lookup data.

    Args:
        badge_ids: Set of valid badge IDs (e.g., {'B0001', 'B0002', ...})
        id_to_badge: Map from employee_id to badge_id (e.g., {1: 'B0001', ...})
        name_to_badge: Map from uppercase full name to badge_id 
                       (e.g., {'CASEY PATEL': 'B0010', ...})

    Returns:
        A normalize_employee_ref function suitable for SQLite UDF registration
    """

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


def build_employee_lookups(
    employees: list[tuple[int, str, str, str]],
) -> tuple[set[str], dict[int, str], dict[str, str]]:
    """
    Build lookup structures for employee normalization.

    Args:
        employees: List of (employee_id, badge_id, first_name, last_name) tuples

    Returns:
        Tuple of (badge_ids set, id_to_badge dict, name_to_badge dict)
    """
    badge_ids: set[str] = set()
    id_to_badge: dict[int, str] = {}
    name_to_badge: dict[str, str] = {}

    for emp_id, badge_id, first_name, last_name in employees:
        badge_ids.add(badge_id)
        id_to_badge[emp_id] = badge_id
        full_name = f"{first_name} {last_name}".upper()
        name_to_badge[full_name] = badge_id

    return badge_ids, id_to_badge, name_to_badge
