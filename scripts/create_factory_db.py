#!/usr/bin/env python3
"""
create_factory_db.py

Creates a SQLite3 database for the factory training exercise and seeds it
with intentionally inconsistent "raw" data.

Usage:
  python scripts/create_factory_db.py data/factory_training.db --seed 42 --overwrite

See MAINT_DATA.md for detailed data specification.
"""

import argparse
import os
import random
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from util.data_helpers import (
    # Constants
    SHIFT_DEFS,
    INCIDENT_TYPE_VARIANTS,
    SEVERITY_VARIANTS,
    ROLE_VARIANTS,
    MAINT_TYPE_VARIANTS,
    BAD_MACHINE_CODES,
    BAD_MACHINE_WEIGHT,
    BAD_EMPLOYEE_WEIGHT,
    NUM_BAD_EMPLOYEES,
    MACHINE_TYPE_MULTIPLIER,
    SHIFT_RISK,
    BASE_INCIDENT_LAMBDA,
    MACHINE_TYPES_SEED,
    INCIDENT_TYPES_SEED,
    ZONES_SEED,
    FIRST_NAMES,
    LAST_NAMES,
    VENDORS,
    INCIDENT_DESCRIPTIONS,
    MAINTENANCE_NOTES,
    # Functions
    iso_now,
    dirty_dt,
    dirty_machine_ref,
    dirty_employee_ref,
    dirty_zone_ref,
    pick_variant,
    maybe_typo,
    make_shift_code,
    choose_incident_type_for_machine,
    choose_severity,
)

SCHEMA_PATH = PROJECT_ROOT / "schema" / "schema.sql"


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class Employee:
    employee_id: int
    badge_id: str
    first_name: str
    last_name: str
    role: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


@dataclass
class Machine:
    machine_id: int
    machine_code: str
    machine_type: str
    machine_type_id: int


# =============================================================================
# REFERENCE DATA SEEDING
# =============================================================================


def seed_reference_tables(cur: sqlite3.Cursor) -> None:
    """Seed machine_types, incident_types, and zones tables."""
    for type_name, category, mtbf in MACHINE_TYPES_SEED:
        cur.execute(
            "INSERT INTO machine_types(type_name, category, typical_mtbf_hours) VALUES (?, ?, ?)",
            (type_name, category, mtbf),
        )

    for incident_type, category, severity in INCIDENT_TYPES_SEED:
        cur.execute(
            "INSERT INTO incident_types(incident_type, category, default_severity) VALUES (?, ?, ?)",
            (incident_type, category, severity),
        )

    for zone_code, zone_name in ZONES_SEED:
        cur.execute(
            "INSERT INTO zones(zone_code, zone_name) VALUES (?, ?)",
            (zone_code, zone_name),
        )


# =============================================================================
# EMPLOYEE GENERATION
# =============================================================================


def generate_employees(
    cur: sqlite3.Cursor, rng: random.Random, n: int = 60
) -> List[Employee]:
    """Generate n employees with realistic distributions."""
    roles = ["Operator", "Technician", "Quality", "Maintenance", "Supervisor"]
    role_weights = [60, 15, 10, 10, 5]

    employees: List[Employee] = []
    used_names = set()

    base_hire = datetime(2018, 1, 1)

    for i in range(1, n + 1):
        # Avoid exact name duplicates
        while True:
            fn = rng.choice(FIRST_NAMES)
            ln = rng.choice(LAST_NAMES)
            key = (fn, ln)
            if key not in used_names:
                used_names.add(key)
                break

        badge = f"B{i:04d}"
        role = rng.choices(roles, weights=role_weights, k=1)[0]
        hire_date = (
            (base_hire + timedelta(days=rng.randint(0, 2200))).date().isoformat()
        )
        status = rng.choices(
            ["active", "leave", "terminated"], weights=[92, 5, 3], k=1
        )[0]

        cur.execute(
            "INSERT INTO employees(badge_id, first_name, last_name, hire_date, role, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (badge, fn, ln, hire_date, role, status),
        )
        emp_id = cur.lastrowid
        employees.append(Employee(emp_id, badge, fn, ln, role))

    return employees


# =============================================================================
# MACHINE GENERATION
# =============================================================================


def generate_machines(
    cur: sqlite3.Cursor, rng: random.Random, n: int = 40
) -> List[Machine]:
    """Generate n machines with type distribution favoring Press and Conveyor."""
    # Fetch machine types
    cur.execute("SELECT machine_type_id, type_name FROM machine_types")
    mt = cur.fetchall()
    type_id_by_name = {name: mid for (mid, name) in mt}

    # Distribution weights
    type_names = list(type_id_by_name.keys())
    weights = []
    for name in type_names:
        if name in ("Press", "Conveyor"):
            weights.append(3.0)
        elif name in ("CNC", "LaserCutter"):
            weights.append(2.0)
        else:
            weights.append(1.5)

    machines: List[Machine] = []
    install_base = datetime(2019, 1, 1)

    for i in range(1, n + 1):
        mcode = f"M-{i:03d}"
        tname = rng.choices(type_names, weights=weights, k=1)[0]
        tid = type_id_by_name[tname]
        vendor = rng.choice(VENDORS)
        install_date = (
            (install_base + timedelta(days=rng.randint(0, 2200))).date().isoformat()
        )
        status = rng.choices(
            ["active", "maintenance", "retired"], weights=[90, 8, 2], k=1
        )[0]

        cur.execute(
            "INSERT INTO machines(machine_code, machine_type_id, vendor, install_date, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (mcode, tid, vendor, install_date, status),
        )
        mid = cur.lastrowid
        machines.append(Machine(mid, mcode, tname, tid))

    return machines


# =============================================================================
# LAYOUT GENERATION
# =============================================================================


def seed_layout_raw(
    cur: sqlite3.Cursor, rng: random.Random, machines: List[Machine]
) -> None:
    """Generate factory layout with dirty machine/zone references."""
    zone_codes = ["Z-01", "Z-02", "Z-03", "Z-04", "Z-05", "Z-06"]

    for m in machines:
        # Place types in plausible zones
        if m.machine_type in ("Press", "CNC", "LaserCutter"):
            zone = rng.choices(["Z-02", "Z-03"], weights=[0.7, 0.3], k=1)[0]
        elif m.machine_type in ("Conveyor", "RobotArm"):
            zone = rng.choices(["Z-03", "Z-04"], weights=[0.6, 0.4], k=1)[0]
        else:
            zone = rng.choices(["Z-01", "Z-05", "Z-03"], weights=[0.2, 0.5, 0.3], k=1)[
                0
            ]

        # Occasional mismatch/outdated zone (5%)
        if rng.random() < 0.05:
            zone = rng.choice(zone_codes)

        x = rng.uniform(0, 100)
        y = rng.uniform(0, 50)
        row_num = rng.randint(1, 10)
        col_num = rng.randint(1, 12)
        eff = dirty_dt(datetime(2023, 1, 1) + timedelta(days=rng.randint(0, 730)), rng)

        cur.execute(
            "INSERT INTO layout_raw(machine_ref_raw, zone_ref_raw, x, y, row_num, col_num, effective_from_raw) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                dirty_machine_ref(m.machine_code, rng),
                dirty_zone_ref(zone, rng),
                x,
                y,
                row_num,
                col_num,
                eff,
            ),
        )

    # Add bogus layout rows for non-existent machines
    for _ in range(3):
        bogus_machine = rng.choice(["M-999", "M-000", "MX-404"])
        bogus_zone = rng.choice(["Z-02", "Z-07", "ZONE-UNKNOWN"])
        cur.execute(
            "INSERT INTO layout_raw(machine_ref_raw, zone_ref_raw, x, y, row_num, col_num, effective_from_raw) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                bogus_machine,
                bogus_zone,
                rng.uniform(0, 100),
                rng.uniform(0, 50),
                rng.randint(1, 10),
                rng.randint(1, 12),
                dirty_dt(datetime(2024, 6, 1), rng),
            ),
        )


# =============================================================================
# SHIFTS AND ASSIGNMENTS
# =============================================================================


def seed_shifts_and_assignments(
    cur: sqlite3.Cursor,
    rng: random.Random,
    employees: List[Employee],
    start_day: datetime,
    end_day: datetime,
    avg_team_size: int = 18,
) -> Tuple[List[str], Dict[str, List[Employee]]]:
    """
    Generate shifts and assignments for date range.

    Returns:
        - List of shift codes
        - Mapping of shift_code -> assigned employees
    """
    shift_codes: List[str] = []
    assigned: Dict[str, List[Employee]] = {}

    supervisors = [e for e in employees if e.role == "Supervisor"]
    if not supervisors:
        supervisors = employees[:5]

    day = start_day
    while day <= end_day:
        for shift_name, start_hour, end_hour, suffix in SHIFT_DEFS:
            scode = make_shift_code(day, suffix)

            # Actual shift times
            sdt = datetime(day.year, day.month, day.day, start_hour, 0, 0)
            edt = datetime(day.year, day.month, day.day, end_hour, 0, 0)
            if suffix == "N":
                edt = edt + timedelta(days=1)

            # Dirty string representations
            start_raw = dirty_dt(sdt, rng)
            end_raw = dirty_dt(edt, rng)

            sup = rng.choice(supervisors)
            sup_ref = dirty_employee_ref(
                sup.employee_id, sup.badge_id, sup.full_name, rng
            )
            team_code = rng.choice(["A", "B", "C", "D"]) + str(rng.randint(1, 4))

            cur.execute(
                "INSERT INTO shifts_raw(shift_code, shift_name, shift_start_raw, shift_end_raw, "
                "supervisor_ref_raw, team_code, created_at_iso) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (scode, shift_name, start_raw, end_raw, sup_ref, team_code, iso_now()),
            )
            shift_codes.append(scode)

            # Team assignments
            team_size = max(8, int(rng.gauss(avg_team_size, 4)))
            team = rng.sample(employees, k=min(team_size, len(employees)))
            assigned[scode] = team

            for emp in team:
                emp_ref = dirty_employee_ref(
                    emp.employee_id, emp.badge_id, emp.full_name, rng
                )
                role_ref = rng.choice(ROLE_VARIANTS)

                # Clock times with occasional missing values
                cin = sdt + timedelta(minutes=rng.randint(-10, 20))
                cout = edt + timedelta(minutes=rng.randint(-20, 25))

                clock_in_raw = (
                    dirty_dt(cin, rng)
                    if rng.random() > 0.04
                    else rng.choice(["", "n/a", "UNKNOWN"])
                )
                clock_out_raw = (
                    dirty_dt(cout, rng)
                    if rng.random() > 0.06
                    else rng.choice(["", "n/a", "UNKNOWN"])
                )

                cur.execute(
                    "INSERT INTO shift_assignments_raw(shift_code, employee_ref_raw, role_ref_raw, "
                    "clock_in_raw, clock_out_raw, created_at_iso) VALUES (?, ?, ?, ?, ?, ?)",
                    (scode, emp_ref, role_ref, clock_in_raw, clock_out_raw, iso_now()),
                )

        day += timedelta(days=1)

    return shift_codes, assigned


# =============================================================================
# INCIDENTS AND MAINTENANCE
# =============================================================================


def build_machine_zone_lookup(
    cur: sqlite3.Cursor, machines: List[Machine]
) -> Dict[str, str]:
    """Build machine_code -> zone_code mapping from layout_raw (best effort)."""
    default_zone = "Z-03"

    cur.execute("SELECT machine_ref_raw, zone_ref_raw FROM layout_raw")
    rows = cur.fetchall()

    def norm_machine(ref: str) -> str:
        if not ref:
            return ""
        digits = "".join(ch for ch in ref if ch.isdigit())
        return digits.zfill(3) if digits else ""

    zone_by_machine: Dict[str, str] = {m.machine_code: default_zone for m in machines}

    for m in machines:
        md = "".join(ch for ch in m.machine_code if ch.isdigit()).zfill(3)
        candidates = [zr for (mr, zr) in rows if norm_machine(mr) == md and zr]

        if candidates:
            best = None
            for c in candidates:
                c2 = c.strip().upper()
                if c2.startswith("Z-") and len(c2) >= 4:
                    best = c2[:4]
                    break
            if not best:
                best = candidates[0].strip().upper()
            if best.startswith("Z-") and len(best) >= 4:
                zone_by_machine[m.machine_code] = best[:4]

    return zone_by_machine


def seed_incidents_and_maintenance(
    cur: sqlite3.Cursor,
    rng: random.Random,
    employees: List[Employee],
    machines: List[Machine],
    shift_codes: List[str],
    assigned: Dict[str, List[Employee]],
    start_day: datetime,
) -> int:
    """
    Generate incidents and correlated maintenance logs.

    Returns count of incidents created.
    """
    # Build outlier sets
    machine_codes = [m.machine_code for m in machines]
    bad_machine_codes = set(c for c in BAD_MACHINE_CODES if c in machine_codes)

    # Add random bad machines if needed
    if len(bad_machine_codes) < 3:
        additional = rng.sample(machine_codes, k=min(3, len(machine_codes)))
        bad_machine_codes.update(additional)

    bad_employee_ids = set(
        e.employee_id
        for e in rng.sample(employees, k=min(NUM_BAD_EMPLOYEES, len(employees)))
    )

    # Machine -> zone mapping
    zone_by_machine = build_machine_zone_lookup(cur, machines)

    incidents_created = 0

    for scode in shift_codes:
        suffix = scode.split("-")[-1]
        lam = BASE_INCIDENT_LAMBDA * SHIFT_RISK.get(suffix, 1.0)

        # Adjust by team composition
        team = assigned.get(scode, [])
        bad_present = sum(1 for e in team if e.employee_id in bad_employee_ids)
        lam *= 1.0 + 0.08 * bad_present

        # Pseudo-Poisson: roll 4 times
        k = 0
        for _ in range(4):
            if rng.random() < min(0.95, lam / 2.0):
                k += 1
        if k == 0 and rng.random() < 0.08 * lam:
            k = 1

        if k == 0:
            continue

        # Parse shift date and times
        day = datetime.strptime(scode.split("-")[1], "%Y%m%d")
        shift_times = {"D": (6, 14), "S": (14, 22), "N": (22, 30)}
        sh_start, sh_end = shift_times.get(suffix, (6, 14))

        sdt = datetime(day.year, day.month, day.day, sh_start, 0, 0)
        edt = datetime(day.year, day.month, day.day, min(sh_end, 23), 59, 59)
        if suffix == "N":
            edt = datetime(day.year, day.month, day.day, 23, 59, 59) + timedelta(
                hours=6
            )

        cluster_anchor = None  # Track cluster center for cascading incidents

        for i in range(k):
            # Select machine (weighted by type + bad status)
            weights = []
            for m in machines:
                w = MACHINE_TYPE_MULTIPLIER.get(m.machine_type, 1.0)
                if m.machine_code in bad_machine_codes:
                    w *= BAD_MACHINE_WEIGHT
                weights.append(w)
            machine = rng.choices(machines, weights=weights, k=1)[0]

            # Select employee (prefer team, weight bad employees)
            if team and rng.random() < 0.85:
                team_weights = []
                for e in team:
                    w = 1.0
                    if e.employee_id in bad_employee_ids:
                        w *= BAD_EMPLOYEE_WEIGHT
                    if e.role in ("Operator", "Technician"):
                        w *= 1.2
                    team_weights.append(w)
                emp = rng.choices(team, weights=team_weights, k=1)[0]
            else:
                emp = rng.choice(employees)

            # Incident time within shift - with clustering tendency
            # First incident or 40% chance: pick fresh random time
            # Otherwise: cluster near previous incident (within ±2 hours)
            if i == 0 or rng.random() < 0.4:
                delta_seconds = rng.randint(0, int((edt - sdt).total_seconds()))
                cluster_anchor = sdt + timedelta(seconds=delta_seconds)
                inc_time = cluster_anchor
            else:
                # Cluster near previous incident
                offset_minutes = rng.randint(-120, 120)  # ±2 hours
                inc_time = cluster_anchor + timedelta(minutes=offset_minutes)
                # Clamp to shift bounds
                inc_time = max(sdt, min(edt, inc_time))
                cluster_anchor = inc_time  # Update anchor for next potential cluster

            rep_time = inc_time + timedelta(minutes=rng.randint(1, 180))

            canonical_type = choose_incident_type_for_machine(machine.machine_type, rng)
            severity_key = choose_severity(canonical_type, rng)

            incident_type_raw = maybe_typo(
                pick_variant(INCIDENT_TYPE_VARIANTS, canonical_type, rng), rng
            )
            severity_raw = maybe_typo(
                pick_variant(SEVERITY_VARIANTS, severity_key, rng), rng
            )

            # Generate dirty references
            machine_ref = dirty_machine_ref(machine.machine_code, rng)
            zone_code = zone_by_machine.get(machine.machine_code, "Z-03")
            zone_ref = dirty_zone_ref(zone_code, rng)

            # Occasional zone mismatch (7%)
            if rng.random() < 0.07:
                zone_ref = dirty_zone_ref(
                    rng.choice(["Z-01", "Z-02", "Z-03", "Z-04", "Z-05", "Z-06"]), rng
                )

            employee_ref = dirty_employee_ref(
                emp.employee_id, emp.badge_id, emp.full_name, rng
            )

            # Shift reference (6% chance of missing/wrong)
            if rng.random() < 0.06:
                shift_ref = rng.choice(
                    [None, "", "n/a", make_shift_code(day, rng.choice(["D", "S", "N"]))]
                )
            else:
                shift_ref = rng.choice([scode, scode.lower(), f" {scode} "])

            description = rng.choice(INCIDENT_DESCRIPTIONS)

            cur.execute(
                "INSERT INTO incident_reports_raw("
                "incident_time_raw, reported_time_raw, shift_code_ref_raw, employee_ref_raw, "
                "machine_ref_raw, zone_ref_raw, incident_type_raw, severity_raw, description, created_at_iso"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    dirty_dt(inc_time, rng),
                    dirty_dt(rep_time, rng),
                    shift_ref,
                    (
                        employee_ref
                        if rng.random() > 0.04
                        else rng.choice(["", "UNKNOWN", None])
                    ),
                    (
                        machine_ref
                        if rng.random() > 0.03
                        else rng.choice(["", "MX-404", None])
                    ),
                    (
                        zone_ref
                        if rng.random() > 0.02
                        else rng.choice(["", "ZONE-UNKNOWN", None])
                    ),
                    incident_type_raw,
                    severity_raw,
                    description,
                    iso_now(),
                ),
            )
            incidents_created += 1

            # Correlated maintenance for machine failures (65%)
            if canonical_type == "machine_failure" and rng.random() < 0.65:
                ms = inc_time + timedelta(minutes=rng.randint(5, 120))
                me = ms + timedelta(minutes=rng.randint(15, 240))
                maint_type = rng.choice(MAINT_TYPE_VARIANTS)
                notes = rng.choice(MAINTENANCE_NOTES)

                cur.execute(
                    "INSERT INTO maintenance_logs_raw(machine_ref_raw, maint_start_raw, maint_end_raw, "
                    "maint_type_raw, notes, created_at_iso) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        dirty_machine_ref(machine.machine_code, rng),
                        dirty_dt(ms, rng),
                        (
                            dirty_dt(me, rng)
                            if rng.random() > 0.08
                            else rng.choice(["", "n/a"])
                        ),
                        maybe_typo(maint_type, rng),
                        notes,
                        iso_now(),
                    ),
                )

    # Add random preventive maintenance (not tied to incidents)
    for _ in range(35):
        m = rng.choice(machines)
        day_offset = rng.randint(0, 730)
        ms = start_day + timedelta(
            days=day_offset, hours=rng.randint(0, 23), minutes=rng.randint(0, 59)
        )
        me = ms + timedelta(minutes=rng.randint(20, 180))

        cur.execute(
            "INSERT INTO maintenance_logs_raw(machine_ref_raw, maint_start_raw, maint_end_raw, "
            "maint_type_raw, notes, created_at_iso) VALUES (?, ?, ?, ?, ?, ?)",
            (
                dirty_machine_ref(m.machine_code, rng),
                dirty_dt(ms, rng),
                dirty_dt(me, rng),
                rng.choice(["Preventive", "PREV", "Inspection", "INSP"]),
                "Scheduled maintenance window.",
                iso_now(),
            ),
        )

    return incidents_created


# =============================================================================
# MAIN
# =============================================================================


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Create and seed factory training database"
    )
    ap.add_argument("db_path", help="Path to SQLite database file to create")
    ap.add_argument(
        "--seed", type=int, default=42, help="Random seed for reproducible data"
    )
    ap.add_argument(
        "--overwrite", action="store_true", help="Overwrite if db file exists"
    )
    ap.add_argument("--start", default="2024-01-01", help="Start date (yyyy-mm-dd)")
    ap.add_argument("--end", default="2025-12-31", help="End date (yyyy-mm-dd)")
    ap.add_argument("--employees", type=int, default=60, help="Number of employees")
    ap.add_argument("--machines", type=int, default=40, help="Number of machines")
    args = ap.parse_args()

    if os.path.exists(args.db_path):
        if not args.overwrite:
            raise SystemExit(
                f"DB already exists: {args.db_path} (use --overwrite to replace)"
            )
        os.remove(args.db_path)

    # Ensure output directory exists
    db_dir = os.path.dirname(args.db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    rng = random.Random(args.seed)

    conn = sqlite3.connect(args.db_path)
    cur = conn.cursor()

    # Load and execute schema
    schema_sql = SCHEMA_PATH.read_text()
    cur.executescript(schema_sql)

    # Seed reference tables
    seed_reference_tables(cur)

    # Generate dimension data
    employees = generate_employees(cur, rng, n=args.employees)
    machines = generate_machines(cur, rng, n=args.machines)

    # Generate layout
    seed_layout_raw(cur, rng, machines)

    # Generate shifts and assignments
    start_day = datetime.strptime(args.start, "%Y-%m-%d")
    end_day = datetime.strptime(args.end, "%Y-%m-%d")
    shift_codes, assigned = seed_shifts_and_assignments(
        cur, rng, employees, start_day, end_day
    )

    # Generate incidents and maintenance
    incidents = seed_incidents_and_maintenance(
        cur, rng, employees, machines, shift_codes, assigned, start_day
    )

    conn.commit()
    conn.close()

    print(f"Created and seeded: {args.db_path}")
    print(f"  Employees: {len(employees)}")
    print(f"  Machines: {len(machines)}")
    print(f"  Shifts: {len(shift_codes)} ({args.start} to {args.end})")
    print(f"  Incidents: {incidents}")


if __name__ == "__main__":
    main()
