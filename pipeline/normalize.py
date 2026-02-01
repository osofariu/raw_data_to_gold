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
