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
