#!/usr/bin/env python3
"""
Scenario 1: Which 3 machines have the most incidents?

This script creates layered views for data cleaning, then materializes
them to tables so they can be queried from any SQL tool.

Architecture (per DATA_CLEANING_APPROACH.md):
  - Views define the transformation logic (clear lineage, easy to debug)
  - Tables materialize the results (queryable from sqlite3 CLI, DBeaver, etc)

Usage:
    uv run python pipeline/run_scenario1.py

After running, use the SQL queries in problems/scenario1.md to explore the results.
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.normalize import normalize_machine_ref

DB_PATH = Path(__file__).parent.parent / "data" / "factory_training.db"


def create_views(conn: sqlite3.Connection) -> None:
    """Create layered views for incident normalization.

    Views define the transformation logic with clear lineage.
    Note: These views require the Python UDF to be registered.
    """

    # Layer 1: Normalize raw fields
    conn.execute("DROP VIEW IF EXISTS v_incidents_normalized")
    conn.execute(
        """
        CREATE VIEW v_incidents_normalized AS
        SELECT 
            incident_id,
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
            normalize_machine_ref(machine_ref_raw) as machine_code
        FROM incident_reports_raw
    """
    )

    # Layer 2: Resolve to foreign keys
    conn.execute("DROP VIEW IF EXISTS v_incidents_resolved")
    conn.execute(
        """
        CREATE VIEW v_incidents_resolved AS
        SELECT 
            n.*,
            m.machine_id
        FROM v_incidents_normalized n
        LEFT JOIN machines m ON n.machine_code = m.machine_code
    """
    )

    print("✓ Created views: v_incidents_normalized, v_incidents_resolved")


def materialize_tables(conn: sqlite3.Connection) -> None:
    """Materialize views to tables for querying from any SQL tool.

    Since the views use Python UDFs, they only work within this Python session.
    We materialize to tables so users can query from sqlite3 CLI, DBeaver, etc.
    """

    # Materialize Layer 1
    conn.execute("DROP TABLE IF EXISTS incidents_normalized")
    conn.execute(
        """
        CREATE TABLE incidents_normalized AS
        SELECT * FROM v_incidents_normalized
    """
    )

    # Materialize Layer 2
    conn.execute("DROP TABLE IF EXISTS incidents_resolved")
    conn.execute(
        """
        CREATE TABLE incidents_resolved AS
        SELECT * FROM v_incidents_resolved
    """
    )

    conn.commit()
    print("✓ Materialized tables: incidents_normalized, incidents_resolved")


def main():
    print("Scenario 1: Creating views and materializing tables...")

    conn = sqlite3.connect(DB_PATH)

    # Register the Python function so it can be used in SQL
    conn.create_function("normalize_machine_ref", 1, normalize_machine_ref)

    try:
        create_views(conn)
        materialize_tables(conn)
    finally:
        conn.close()

    print(
        "\nNext: Run the SQL queries in problems/scenario1.md to explore the results."
    )


if __name__ == "__main__":
    main()
