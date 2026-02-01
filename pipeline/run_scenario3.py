#!/usr/bin/env python3
"""
Scenario 3: Which 5 employees appear in the most incidents?

This script creates views and tables to normalize employee references,
enabling incident counts per employee.

Unlike machine/shift normalization, employee normalization requires
lookups for name matching. We load the employees table and create
a normalizer closure that has access to the lookup data.

Usage:
    uv run python pipeline/run_scenario3.py

After running, use the SQL queries in problems/scenario3.md to explore the results.
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.normalize import create_employee_normalizer, build_employee_lookups

DB_PATH = Path(__file__).parent.parent / "data" / "factory_training.db"


def load_employees(conn: sqlite3.Connection) -> list[tuple[int, str, str, str]]:
    """Load employee data for building lookups."""
    cursor = conn.execute(
        "SELECT employee_id, badge_id, first_name, last_name FROM employees"
    )
    return cursor.fetchall()


def create_views(conn: sqlite3.Connection) -> None:
    """Create views for normalizing employee references."""

    conn.execute("DROP VIEW IF EXISTS v_incidents_with_employee")
    conn.execute("""
        CREATE VIEW v_incidents_with_employee AS
        SELECT 
            incident_id,
            incident_time_raw,
            reported_time_raw,
            shift_code_ref_raw,
            employee_ref_raw,
            normalize_employee_ref(employee_ref_raw) as badge_id,
            machine_ref_raw,
            zone_ref_raw,
            incident_type_raw,
            severity_raw,
            description,
            created_at_iso
        FROM incident_reports_raw
    """)

    print("✓ Created view: v_incidents_with_employee")


def materialize_tables(conn: sqlite3.Connection) -> None:
    """Materialize views to tables for querying."""

    conn.execute("DROP TABLE IF EXISTS incidents_with_employee")
    conn.execute("""
        CREATE TABLE incidents_with_employee AS
        SELECT * FROM v_incidents_with_employee
    """)

    conn.commit()
    print("✓ Materialized table: incidents_with_employee")


def main():
    print("Scenario 3: Creating views and tables for employee analysis...")

    conn = sqlite3.connect(DB_PATH)

    # Load employees and build lookups
    employees = load_employees(conn)
    badge_ids, id_to_badge, name_to_badge = build_employee_lookups(employees)
    print(f"✓ Loaded {len(employees)} employees for lookup")

    # Create the normalizer with employee data baked in
    normalize_employee_ref = create_employee_normalizer(
        badge_ids, id_to_badge, name_to_badge
    )

    # Register the Python function so it can be used in SQL
    conn.create_function("normalize_employee_ref", 1, normalize_employee_ref)

    try:
        create_views(conn)
        materialize_tables(conn)
    finally:
        conn.close()

    print("\nNext: Run the SQL queries in problems/scenario3.md to explore the results.")


if __name__ == "__main__":
    main()
