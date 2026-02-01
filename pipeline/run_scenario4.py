#!/usr/bin/env python3
"""
Scenario 4: Which machine type has the highest failure rate?

This script creates views and tables that normalize both incident_type
and machine_ref, enabling failure rate calculations per machine type.

Reuses: normalize_machine_ref from Scenario 1
New: normalize_incident_type

Usage:
    uv run python pipeline/run_scenario4.py

After running, use the SQL queries in problems/scenario4.md to explore the results.
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.normalize import normalize_machine_ref, normalize_incident_type

DB_PATH = Path(__file__).parent.parent / "data" / "factory_training.db"


def create_views(conn: sqlite3.Connection) -> None:
    """Create views for normalizing incident type and machine references."""

    # Full incident normalization view (combines multiple normalizations)
    conn.execute("DROP VIEW IF EXISTS v_incidents_full")
    conn.execute(
        """
        CREATE VIEW v_incidents_full AS
        SELECT 
            incident_id,
            incident_time_raw,
            reported_time_raw,
            shift_code_ref_raw,
            employee_ref_raw,
            machine_ref_raw,
            normalize_machine_ref(machine_ref_raw) as machine_code,
            zone_ref_raw,
            incident_type_raw,
            normalize_incident_type(incident_type_raw) as incident_type,
            severity_raw,
            description,
            created_at_iso
        FROM incident_reports_raw
    """
    )

    print("✓ Created view: v_incidents_full")


def materialize_tables(conn: sqlite3.Connection) -> None:
    """Materialize views to tables for querying."""

    conn.execute("DROP TABLE IF EXISTS incidents_full")
    conn.execute(
        """
        CREATE TABLE incidents_full AS
        SELECT * FROM v_incidents_full
    """
    )

    conn.commit()
    print("✓ Materialized table: incidents_full")


def main():
    print("Scenario 4: Creating views and tables for failure rate analysis...")

    conn = sqlite3.connect(DB_PATH)

    # Register the Python functions so they can be used in SQL
    conn.create_function("normalize_machine_ref", 1, normalize_machine_ref)
    conn.create_function("normalize_incident_type", 1, normalize_incident_type)

    try:
        create_views(conn)
        materialize_tables(conn)
    finally:
        conn.close()

    print(
        "\nNext: Run the SQL queries in problems/scenario4.md to explore the results."
    )


if __name__ == "__main__":
    main()
