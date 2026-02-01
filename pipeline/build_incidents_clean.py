#!/usr/bin/env python3
"""
Consolidated Data Cleaning Pipeline

Creates a single comprehensive view and table with ALL normalizations applied.
This replaces the need for multiple scenario-specific tables.

Output:
    - v_incidents_clean: View with all normalization logic
    - incidents_clean: Materialized table for querying

Usage:
    uv run python pipeline/build_incidents_clean.py

After running, all scenarios can query from the single incidents_clean table.
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.normalize import (
    normalize_machine_ref,
    normalize_shift_code,
    normalize_incident_type,
    create_employee_normalizer,
    parse_incident_time,
)

DB_PATH = Path(__file__).parent.parent / "data" / "factory_training.db"


def load_employees(conn: sqlite3.Connection) -> list[tuple[int, str, str, str]]:
    """Load employee data for building lookups."""
    cursor = conn.execute(
        "SELECT employee_id, badge_id, first_name, last_name FROM employees"
    )
    return cursor.fetchall()


def register_udfs(conn: sqlite3.Connection, employees: list) -> None:
    """Register all normalization functions as SQLite UDFs."""

    conn.create_function("normalize_machine_ref", 1, normalize_machine_ref)
    conn.create_function("normalize_shift_code", 1, normalize_shift_code)
    conn.create_function("normalize_incident_type", 1, normalize_incident_type)
    conn.create_function("parse_incident_time", 1, parse_incident_time)

    # Employee normalizer needs lookup data baked in
    normalize_employee_ref = create_employee_normalizer(employees)
    conn.create_function("normalize_employee_ref", 1, normalize_employee_ref)

    print("✓ Registered 5 normalization UDFs")


def create_view(conn: sqlite3.Connection) -> None:
    """Create the comprehensive incidents view with all normalizations."""

    conn.execute("DROP VIEW IF EXISTS v_incidents_clean")
    conn.execute(
        """
        CREATE VIEW v_incidents_clean AS
        SELECT 
            incident_id,
            
            -- Raw columns preserved for debugging
            incident_time_raw,
            reported_time_raw,
            shift_code_ref_raw,
            employee_ref_raw,
            machine_ref_raw,
            zone_ref_raw,
            incident_type_raw,
            severity_raw,
            description,
            created_at_iso,
            
            -- Normalized columns
            normalize_machine_ref(machine_ref_raw) as machine_code,
            normalize_shift_code(shift_code_ref_raw) as shift_code,
            normalize_employee_ref(employee_ref_raw) as badge_id,
            normalize_incident_type(incident_type_raw) as incident_type,
            parse_incident_time(incident_time_raw) as incident_time
            
        FROM incident_reports_raw
    """
    )

    print("✓ Created view: v_incidents_clean")


def materialize_table(conn: sqlite3.Connection) -> None:
    """Materialize the view to a table for querying."""

    conn.execute("DROP TABLE IF EXISTS incidents_clean")
    conn.execute("CREATE TABLE incidents_clean AS SELECT * FROM v_incidents_clean")
    conn.commit()

    # Report stats
    cursor = conn.execute("SELECT COUNT(*) FROM incidents_clean")
    total = cursor.fetchone()[0]

    cursor = conn.execute(
        """
        SELECT 
            SUM(CASE WHEN machine_code IS NOT NULL THEN 1 ELSE 0 END) as machines,
            SUM(CASE WHEN shift_code IS NOT NULL THEN 1 ELSE 0 END) as shifts,
            SUM(CASE WHEN badge_id IS NOT NULL THEN 1 ELSE 0 END) as employees,
            SUM(CASE WHEN incident_type IS NOT NULL THEN 1 ELSE 0 END) as types,
            SUM(CASE WHEN incident_time IS NOT NULL THEN 1 ELSE 0 END) as times
        FROM incidents_clean
    """
    )
    machines, shifts, employees, types, times = cursor.fetchone()

    print(f"✓ Materialized table: incidents_clean ({total} rows)")
    print(
        f"  Match rates: machine={100*machines/total:.1f}%, shift={100*shifts/total:.1f}%, "
        f"employee={100*employees/total:.1f}%, type={100*types/total:.1f}%, time={100*times/total:.1f}%"
    )


def main():
    print("Running consolidated data cleaning pipeline...\n")

    conn = sqlite3.connect(DB_PATH)

    try:
        # Load lookup data
        employees = load_employees(conn)
        print(f"✓ Loaded {len(employees)} employees for lookup")

        # Register all UDFs
        register_udfs(conn, employees)

        # Create view and table
        create_view(conn)
        materialize_table(conn)

    finally:
        conn.close()

    print("\n✓ Pipeline complete. Query from: incidents_clean")


if __name__ == "__main__":
    main()
