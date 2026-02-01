#!/usr/bin/env python3
"""
Scenario 2: Is the night shift really more dangerous?

This script creates views and tables to join incidents with shifts,
enabling incident rate calculations per shift type.

Architecture:
  - Views define the transformation logic (clear lineage)
  - Tables materialize the results (queryable from any SQL tool)

Usage:
    uv run python pipeline/run_scenario2.py

After running, use the SQL queries in problems/scenario2.md to explore the results.
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.normalize import normalize_shift_code

DB_PATH = Path(__file__).parent.parent / "data" / "factory_training.db"


def create_views(conn: sqlite3.Connection) -> None:
    """Create views for joining incidents to shifts."""

    # View: Normalize shift_code_ref_raw and include all incident fields
    conn.execute("DROP VIEW IF EXISTS v_incidents_with_shift")
    conn.execute(
        """
        CREATE VIEW v_incidents_with_shift AS
        SELECT 
            incident_id,
            incident_time_raw,
            reported_time_raw,
            shift_code_ref_raw,
            normalize_shift_code(shift_code_ref_raw) as shift_code,
            employee_ref_raw,
            machine_ref_raw,
            zone_ref_raw,
            incident_type_raw,
            severity_raw,
            description,
            created_at_iso
        FROM incident_reports_raw
    """
    )

    print("✓ Created view: v_incidents_with_shift")


def materialize_tables(conn: sqlite3.Connection) -> None:
    """Materialize views to tables for querying."""

    conn.execute("DROP TABLE IF EXISTS incidents_with_shift")
    conn.execute(
        """
        CREATE TABLE incidents_with_shift AS
        SELECT * FROM v_incidents_with_shift
    """
    )

    conn.commit()
    print("✓ Materialized table: incidents_with_shift")


def main():
    print("Scenario 2: Creating views and tables for shift analysis...")

    conn = sqlite3.connect(DB_PATH)

    # Register the Python function so it can be used in SQL
    conn.create_function("normalize_shift_code", 1, normalize_shift_code)

    try:
        create_views(conn)
        materialize_tables(conn)
    finally:
        conn.close()

    print(
        "\nNext: Run the SQL queries in problems/scenario2.md to explore the results."
    )


if __name__ == "__main__":
    main()
