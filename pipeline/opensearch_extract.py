#!/usr/bin/env python3
"""
Extract data from SQLite and denormalize for OpenSearch indexing.

Reads from incidents_clean (which has all normalized fields) and
enriches with lookup data from dimension tables.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterator

DB_PATH = Path(__file__).parent.parent / "data" / "factory_training.db"


def load_lookup_tables(conn: sqlite3.Connection) -> dict:
    """Load all lookup tables for denormalization."""
    lookups = {}

    # Employees: badge_id -> employee details
    cursor = conn.execute(
        "SELECT badge_id, first_name, last_name, role FROM employees"
    )
    lookups["employees"] = {
        row[0]: {
            "badge_id": row[0],
            "first_name": row[1],
            "last_name": row[2],
            "full_name": f"{row[1]} {row[2]}",
            "role": row[3],
        }
        for row in cursor.fetchall()
    }

    # Machines: machine_code -> machine details
    cursor = conn.execute(
        """
        SELECT m.machine_code, mt.type_name, mt.category, m.vendor
        FROM machines m
        LEFT JOIN machine_types mt ON m.machine_type_id = mt.machine_type_id
        """
    )
    lookups["machines"] = {
        row[0]: {
            "code": row[0],
            "type": row[1],
            "category": row[2],
            "vendor": row[3],
        }
        for row in cursor.fetchall()
    }

    # Zones: zone_code -> zone details
    cursor = conn.execute("SELECT zone_code, zone_name FROM zones")
    lookups["zones"] = {
        row[0]: {"zone_code": row[0], "zone_name": row[1]}
        for row in cursor.fetchall()
    }

    # Shifts: shift_code -> shift details
    cursor = conn.execute("SELECT shift_code, shift_name FROM shifts_raw")
    lookups["shifts"] = {
        row[0]: {"code": row[0], "name": row[1]}
        for row in cursor.fetchall()
    }

    return lookups


def extract_incidents(conn: sqlite3.Connection) -> list[dict]:
    """Extract all incidents from incidents_clean (normalized fields only)."""
    cursor = conn.execute(
        """
        SELECT 
            incident_id,
            incident_type,
            severity,
            description,
            machine_code,
            badge_id,
            zone_code,
            shift_code,
            incident_time,
            reported_time
        FROM incidents_clean
        """
    )

    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def to_iso8601(dt_str: str | None) -> str | None:
    """Convert 'YYYY-MM-DD HH:MM:SS' to ISO 8601 'YYYY-MM-DDTHH:MM:SS'."""
    if dt_str is None:
        return None
    # Replace space with T for ISO 8601 compliance
    return dt_str.replace(" ", "T")


def denormalize_incident(incident: dict, lookups: dict) -> dict:
    """
    Transform a single incident row into a denormalized document.
    
    This is the key transformation step - we embed related data
    directly into the document for efficient searching.
    
    Only clean/normalized fields are included (no *_raw fields).
    """
    now = datetime.utcnow().isoformat()

    # Get related entities (with safe defaults)
    machine_code = incident.get("machine_code")
    machine = lookups["machines"].get(machine_code, {}) if machine_code else {}

    badge_id = incident.get("badge_id")
    employee = lookups["employees"].get(badge_id, {}) if badge_id else {}

    zone_code = incident.get("zone_code")
    zone = lookups["zones"].get(zone_code, {}) if zone_code else {}

    shift_code = incident.get("shift_code")
    shift = lookups["shifts"].get(shift_code, {}) if shift_code else {}

    return {
        "incident_id": incident["incident_id"],
        "timestamp": {
            "incident_time": to_iso8601(incident.get("incident_time")),
            "reported_time": to_iso8601(incident.get("reported_time")),
            "indexed_at": now,
        },
        "incident": {
            "type": incident.get("incident_type"),
            "severity": incident.get("severity"),
            "description": incident.get("description"),
        },
        "machine": {
            "code": machine_code,
            "type": machine.get("type"),
            "category": machine.get("category"),
            "vendor": machine.get("vendor"),
        },
        "employee": {
            "badge_id": badge_id,
            "first_name": employee.get("first_name"),
            "last_name": employee.get("last_name"),
            "full_name": employee.get("full_name"),
            "role": employee.get("role"),
        },
        "location": {
            "zone_code": zone_code,
            "zone_name": zone.get("zone_name"),
        },
        "shift": {
            "code": shift_code,
            "name": shift.get("name"),
        },
    }


def generate_documents(db_path: Path = DB_PATH) -> Iterator[dict]:
    """
    Main extraction function - yields denormalized documents.
    
    Usage:
        for doc in generate_documents():
            # index doc to OpenSearch
    """
    conn = sqlite3.connect(db_path)
    try:
        print("Loading lookup tables for denormalization...")
        lookups = load_lookup_tables(conn)
        print(f"  {len(lookups['employees'])} employees")
        print(f"  {len(lookups['machines'])} machines")
        print(f"  {len(lookups['zones'])} zones")
        print(f"  {len(lookups['shifts'])} shifts")

        print("Extracting incidents...")
        incidents = extract_incidents(conn)
        print(f"  {len(incidents)} incidents to process")

        print("Denormalizing...")
        for incident in incidents:
            yield denormalize_incident(incident, lookups)

    finally:
        conn.close()
