#!/usr/bin/env python3
"""
append_factory_data.py

Appends new "raw" data to an existing factory training SQLite DB:
- Adds N days of new shifts + assignments
- Adds incidents/maintenance following the same bias/outlier model

Usage:
  python scripts/append_factory_data.py data/factory_training.db --days 30 --seed 100

See MAINT_DATA.md for detailed data specification.
"""

import argparse
import random
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple

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


# =============================================================================
# DATABASE QUERIES
# =============================================================================

def get_latest_shift_day(conn: sqlite3.Connection) -> datetime:
    """Find the latest day from shift_code pattern S-YYYYMMDD-?."""
    cur = conn.cursor()
    cur.execute("SELECT MAX(shift_code) FROM shifts_raw")
    row = cur.fetchone()
    
    if not row or not row[0]:
        raise RuntimeError("No shifts found in shifts_raw. Did you seed the DB first?")
    
    max_code = row[0].strip().upper()
    parts = max_code.split("-")
    # expected: ["S", "YYYYMMDD", "D"]
    day = datetime.strptime(parts[1], "%Y%m%d")
    return day


def fetch_employees(conn: sqlite3.Connection) -> List[Tuple[int, str, str]]:
    """Return list of (employee_id, badge_id, full_name) for active employees."""
    cur = conn.cursor()
    cur.execute(
        "SELECT employee_id, badge_id, first_name, last_name FROM employees "
        "WHERE status != 'terminated'"
    )
    return [(eid, badge, f"{fn} {ln}") for eid, badge, fn, ln in cur.fetchall()]


def fetch_machines(conn: sqlite3.Connection) -> List[Tuple[str, str]]:
    """Return list of (machine_code, type_name) for active machines."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT m.machine_code, mt.type_name
        FROM machines m 
        JOIN machine_types mt ON m.machine_type_id = mt.machine_type_id
        WHERE m.status != 'retired'
        """
    )
    return cur.fetchall()


# =============================================================================
# MAIN APPEND LOGIC
# =============================================================================

def main() -> None:
    ap = argparse.ArgumentParser(description="Append new data to factory database")
    ap.add_argument("db_path", help="Path to existing SQLite database")
    ap.add_argument("--days", type=int, default=30, help="Days of new data to append")
    ap.add_argument("--seed", type=int, default=100, help="Random seed")
    ap.add_argument("--avg_team_size", type=int, default=18, help="Average team size per shift")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    conn = sqlite3.connect(args.db_path)
    conn.execute("PRAGMA foreign_keys=ON;")
    cur = conn.cursor()

    # Find where to start
    latest_day = get_latest_shift_day(conn)
    start_day = latest_day + timedelta(days=1)
    end_day = start_day + timedelta(days=args.days - 1)

    # Load existing entities
    employees = fetch_employees(conn)
    machines = fetch_machines(conn)

    if not employees or not machines:
        raise RuntimeError("Missing employees or machines; DB may be incomplete.")

    # Build outlier sets (consistent with create script)
    machine_codes = [mc for (mc, _) in machines]
    bad_machine_codes = set(c for c in BAD_MACHINE_CODES if c in machine_codes)
    if len(bad_machine_codes) < 2:
        bad_machine_codes.update(rng.sample(machine_codes, k=min(3, len(machine_codes))))

    bad_employee_ids = set(
        eid for (eid, _, _) in rng.sample(employees, k=min(NUM_BAD_EMPLOYEES, len(employees)))
    )

    zone_codes = ["Z-01", "Z-02", "Z-03", "Z-04", "Z-05", "Z-06"]

    day = start_day
    new_shift_codes: List[str] = []
    incidents_created = 0

    while day <= end_day:
        for shift_name, start_hour, end_hour, suffix in SHIFT_DEFS:
            scode = make_shift_code(day, suffix)

            sdt = datetime(day.year, day.month, day.day, start_hour, 0, 0)
            edt = datetime(day.year, day.month, day.day, end_hour, 0, 0)
            if suffix == "N":
                edt += timedelta(days=1)

            # Supervisor reference
            sup_eid, sup_badge, sup_name = rng.choice(employees)
            supervisor_ref_raw = dirty_employee_ref(sup_eid, sup_badge, sup_name, rng)

            cur.execute(
                "INSERT INTO shifts_raw(shift_code, shift_name, shift_start_raw, shift_end_raw, "
                "supervisor_ref_raw, team_code, created_at_iso) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    scode,
                    shift_name,
                    dirty_dt(sdt, rng),
                    dirty_dt(edt, rng),
                    supervisor_ref_raw,
                    rng.choice(["A", "B", "C", "D"]) + str(rng.randint(1, 4)),
                    iso_now(),
                ),
            )
            new_shift_codes.append(scode)

            # Team assignments
            team_size = max(8, int(rng.gauss(args.avg_team_size, 4)))
            team = rng.sample(employees, k=min(team_size, len(employees)))

            for eid, badge, name in team:
                cur.execute(
                    "INSERT INTO shift_assignments_raw(shift_code, employee_ref_raw, role_ref_raw, "
                    "clock_in_raw, clock_out_raw, created_at_iso) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        scode,
                        dirty_employee_ref(eid, badge, name, rng),
                        rng.choice(ROLE_VARIANTS),
                        (
                            dirty_dt(sdt + timedelta(minutes=rng.randint(-10, 20)), rng)
                            if rng.random() > 0.05
                            else rng.choice(["", "n/a", "UNKNOWN"])
                        ),
                        (
                            dirty_dt(edt + timedelta(minutes=rng.randint(-20, 25)), rng)
                            if rng.random() > 0.08
                            else rng.choice(["", "n/a", "UNKNOWN"])
                        ),
                        iso_now(),
                    ),
                )

            # Generate incidents for this shift
            lam = BASE_INCIDENT_LAMBDA * SHIFT_RISK.get(suffix, 1.0)
            bad_present = sum(1 for (eid, _, _) in team if eid in bad_employee_ids)
            lam *= 1.0 + 0.08 * bad_present

            k = 0
            for _ in range(4):
                if rng.random() < min(0.95, lam / 2.0):
                    k += 1
            if k == 0 and rng.random() < 0.08 * lam:
                k = 1

            if k == 0:
                continue

            # Shift window for incident times
            shift_def = {"D": (6, 14), "S": (14, 22), "N": (22, 30)}
            sh_start, sh_end = shift_def.get(suffix, (6, 14))
            sdt2 = datetime(day.year, day.month, day.day, sh_start, 0, 0)
            if suffix == "N":
                edt2 = datetime(day.year, day.month, day.day, 23, 59, 59) + timedelta(hours=6)
            else:
                edt2 = datetime(day.year, day.month, day.day, sh_end, 0, 0)

            for _ in range(k):
                # Select machine (weighted)
                weights = []
                for mc, mt in machines:
                    w = MACHINE_TYPE_MULTIPLIER.get(mt, 1.0)
                    if mc in bad_machine_codes:
                        w *= BAD_MACHINE_WEIGHT
                    weights.append(w)
                mc, mt = rng.choices(machines, weights=weights, k=1)[0]

                # Select employee
                if team and rng.random() < 0.85:
                    team_weights = []
                    for eid, badge, name in team:
                        w = 1.0
                        if eid in bad_employee_ids:
                            w *= BAD_EMPLOYEE_WEIGHT
                        team_weights.append(w)
                    eid, badge, name = rng.choices(team, weights=team_weights, k=1)[0]
                else:
                    eid, badge, name = rng.choice(employees)

                delta_seconds = rng.randint(0, int((edt2 - sdt2).total_seconds()))
                inc_time = sdt2 + timedelta(seconds=delta_seconds)
                rep_time = inc_time + timedelta(minutes=rng.randint(1, 180))

                canonical_type = choose_incident_type_for_machine(mt, rng)
                severity_key = choose_severity(canonical_type, rng)

                it_raw = maybe_typo(pick_variant(INCIDENT_TYPE_VARIANTS, canonical_type, rng), rng)
                sev_raw = maybe_typo(pick_variant(SEVERITY_VARIANTS, severity_key, rng), rng)

                zone_code = rng.choice(zone_codes)

                cur.execute(
                    "INSERT INTO incident_reports_raw("
                    "incident_time_raw, reported_time_raw, shift_code_ref_raw, employee_ref_raw, "
                    "machine_ref_raw, zone_ref_raw, incident_type_raw, severity_raw, description, created_at_iso"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        dirty_dt(inc_time, rng),
                        dirty_dt(rep_time, rng),
                        (
                            rng.choice([scode, scode.lower(), f" {scode} "])
                            if rng.random() > 0.06
                            else rng.choice([None, "", "n/a"])
                        ),
                        (
                            dirty_employee_ref(eid, badge, name, rng)
                            if rng.random() > 0.05
                            else rng.choice(["", "UNKNOWN", None])
                        ),
                        (
                            dirty_machine_ref(mc, rng)
                            if rng.random() > 0.04
                            else rng.choice(["", "MX-404", None])
                        ),
                        (
                            dirty_zone_ref(zone_code, rng)
                            if rng.random() > 0.03
                            else rng.choice(["", "ZONE-UNKNOWN", None])
                        ),
                        it_raw,
                        sev_raw,
                        rng.choice(INCIDENT_DESCRIPTIONS),
                        iso_now(),
                    ),
                )
                incidents_created += 1

                # Correlated maintenance for machine failures
                if canonical_type == "machine_failure" and rng.random() < 0.65:
                    ms = inc_time + timedelta(minutes=rng.randint(5, 120))
                    me = ms + timedelta(minutes=rng.randint(15, 240))
                    cur.execute(
                        "INSERT INTO maintenance_logs_raw(machine_ref_raw, maint_start_raw, maint_end_raw, "
                        "maint_type_raw, notes, created_at_iso) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            dirty_machine_ref(mc, rng),
                            dirty_dt(ms, rng),
                            (
                                dirty_dt(me, rng)
                                if rng.random() > 0.08
                                else rng.choice(["", "n/a"])
                            ),
                            maybe_typo(rng.choice(MAINT_TYPE_VARIANTS), rng),
                            rng.choice(MAINTENANCE_NOTES),
                            iso_now(),
                        ),
                    )

        day += timedelta(days=1)

    conn.commit()
    conn.close()

    print(f"Appended {args.days} days of data to {args.db_path}")
    print(f"  Date range: {start_day.date()} to {end_day.date()}")
    print(f"  New shifts: {len(new_shift_codes)}")
    print(f"  New incidents: {incidents_created}")


if __name__ == "__main__":
    main()
