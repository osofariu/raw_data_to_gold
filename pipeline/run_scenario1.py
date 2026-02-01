#!/usr/bin/env python3
"""
Scenario 1: Which 3 machines have the most incidents?

This script creates normalized tables to answer the question.
It registers normalize_machine_ref as a SQLite user-defined function,
runs the normalization, and persists results to tables.

Usage:
    uv run python pipeline/run_scenario1.py

After running, use the SQL queries in problems/scenario1.md to explore the results.
The tables can be queried from any SQL tool (sqlite3 CLI, DBeaver, etc).
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.normalize import normalize_machine_ref

DB_PATH = Path(__file__).parent.parent / "data" / "factory_training.db"


def create_tables(conn: sqlite3.Connection) -> None:
    """Create the layered tables for incident normalization.
    
    We use tables (not views) because the normalization uses a Python UDF.
    Tables allow SQL queries to work from any tool (sqlite3 CLI, DBeaver, etc).
    """
    
    # Layer 1: Normalize raw fields
    conn.execute("DROP TABLE IF EXISTS incidents_normalized")
    conn.execute("""
        CREATE TABLE incidents_normalized AS
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
    """)
    
    # Layer 2: Resolve to foreign keys
    conn.execute("DROP TABLE IF EXISTS incidents_resolved")
    conn.execute("""
        CREATE TABLE incidents_resolved AS
        SELECT 
            n.*,
            m.machine_id
        FROM incidents_normalized n
        LEFT JOIN machines m ON n.machine_code = m.machine_code
    """)
    
    conn.commit()
    print("✓ Created tables: incidents_normalized, incidents_resolved")


def main():
    print("Scenario 1: Creating normalized tables...")
    
    conn = sqlite3.connect(DB_PATH)
    
    # Register the Python function so it can be used in SQL
    conn.create_function("normalize_machine_ref", 1, normalize_machine_ref)
    
    try:
        create_tables(conn)
    finally:
        conn.close()
    
    print("\nNext: Run the SQL queries in problems/scenario1.md to explore the results.")


if __name__ == "__main__":
    main()
