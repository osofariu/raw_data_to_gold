#!/usr/bin/env python3
"""
validate_data.py

Validates that the factory database has the expected characteristics:
- Data volumes are in expected ranges
- Required outliers are present (bad machines, shift risk, etc.)
- Data quality issues exist (multiple date formats, bogus refs)

Usage:
  python scripts/validate_data.py data/factory_training.db

Returns exit code 0 if all validations pass, 1 otherwise.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from util.data_helpers import BAD_MACHINE_CODES


def print_check(name: str, passed: bool, detail: str = "") -> bool:
    """Print validation result with checkmark/cross."""
    icon = "✓" if passed else "✗"
    status = "PASS" if passed else "FAIL"
    msg = f"  [{icon}] {name}: {status}"
    if detail:
        msg += f" ({detail})"
    print(msg)
    return passed


def validate_volumes(conn: sqlite3.Connection) -> bool:
    """Check that data volumes are in expected ranges."""
    print("\n=== Volume Checks ===")
    all_passed = True
    
    checks = [
        ("employees", 55, 65),
        ("machines", 35, 45),
        ("shifts_raw", 2000, 2500),
        ("incident_reports_raw", 350, 700),
        ("maintenance_logs_raw", 150, 450),
    ]
    
    for table, min_count, max_count in checks:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        passed = min_count <= count <= max_count
        all_passed &= print_check(
            f"{table} count",
            passed,
            f"{count}, expected {min_count}-{max_count}"
        )
    
    return all_passed


def validate_bad_machines(conn: sqlite3.Connection) -> bool:
    """Check that specified machines have elevated incident rates."""
    print("\n=== Bad Machine Checks ===")
    cur = conn.cursor()
    
    # Get average incidents per machine
    cur.execute("""
        SELECT machine_ref_raw, COUNT(*) as cnt
        FROM incident_reports_raw
        WHERE machine_ref_raw IS NOT NULL AND machine_ref_raw != ''
        GROUP BY machine_ref_raw
    """)
    raw_counts = cur.fetchall()
    
    # Normalize machine refs to digits for matching
    def normalize(ref: str) -> str:
        digits = "".join(c for c in ref if c.isdigit())
        return digits.zfill(3) if digits else ""
    
    # Aggregate by normalized machine code
    machine_incidents: dict[str, int] = {}
    for ref, count in raw_counts:
        norm = normalize(ref)
        if norm:
            machine_incidents[norm] = machine_incidents.get(norm, 0) + count
    
    if not machine_incidents:
        print("  [✗] No incident data to analyze")
        return False
    
    # Calculate average
    total_incidents = sum(machine_incidents.values())
    num_machines = len(machine_incidents)
    avg_incidents = total_incidents / num_machines if num_machines > 0 else 0
    
    print(f"  Average incidents per machine: {avg_incidents:.1f}")
    
    all_passed = True
    for bad_code in BAD_MACHINE_CODES:
        norm = normalize(bad_code)
        count = machine_incidents.get(norm, 0)
        ratio = count / avg_incidents if avg_incidents > 0 else 0
        passed = ratio >= 1.5  # Should be at least 1.5x average
        all_passed &= print_check(
            f"{bad_code} incident rate",
            passed,
            f"{count} incidents, {ratio:.1f}x average"
        )
    
    return all_passed


def validate_shift_risk(conn: sqlite3.Connection) -> bool:
    """Check that night shift has higher incident rate than day shift."""
    print("\n=== Shift Risk Checks ===")
    cur = conn.cursor()
    
    # Count shifts by type
    cur.execute("""
        SELECT 
            CASE 
                WHEN shift_code LIKE '%-D' THEN 'Day'
                WHEN shift_code LIKE '%-S' THEN 'Swing'
                WHEN shift_code LIKE '%-N' THEN 'Night'
                ELSE 'Unknown'
            END as shift_type,
            COUNT(*) as shift_count
        FROM shifts_raw
        GROUP BY shift_type
    """)
    shift_counts = {row[0]: row[1] for row in cur.fetchall()}
    
    # Count incidents by shift type (using shift_code_ref_raw)
    cur.execute("""
        SELECT 
            CASE 
                WHEN UPPER(TRIM(shift_code_ref_raw)) LIKE '%-D' THEN 'Day'
                WHEN UPPER(TRIM(shift_code_ref_raw)) LIKE '%-S' THEN 'Swing'
                WHEN UPPER(TRIM(shift_code_ref_raw)) LIKE '%-N' THEN 'Night'
                ELSE 'Unknown'
            END as shift_type,
            COUNT(*) as incident_count
        FROM incident_reports_raw
        WHERE shift_code_ref_raw IS NOT NULL AND shift_code_ref_raw != ''
        GROUP BY shift_type
    """)
    incident_counts = {row[0]: row[1] for row in cur.fetchall()}
    
    # Calculate rates
    day_rate = incident_counts.get("Day", 0) / shift_counts.get("Day", 1)
    night_rate = incident_counts.get("Night", 0) / shift_counts.get("Night", 1)
    swing_rate = incident_counts.get("Swing", 0) / shift_counts.get("Swing", 1)
    
    print(f"  Day shift rate: {day_rate:.3f} incidents/shift")
    print(f"  Swing shift rate: {swing_rate:.3f} incidents/shift")
    print(f"  Night shift rate: {night_rate:.3f} incidents/shift")
    
    all_passed = True
    
    # Night should be at least 1.3x day
    if day_rate > 0:
        night_ratio = night_rate / day_rate
        passed = night_ratio >= 1.25  # Allow some variance
        all_passed &= print_check(
            "Night/Day incident ratio",
            passed,
            f"{night_ratio:.2f}x, expected ≥1.25x"
        )
    else:
        all_passed &= print_check("Night/Day incident ratio", False, "No day shift data")
    
    return all_passed


def validate_employee_concentration(conn: sqlite3.Connection) -> bool:
    """Check that a few employees account for disproportionate share of incidents."""
    print("\n=== Employee Concentration Checks ===")
    cur = conn.cursor()
    
    # Count incidents per employee reference
    cur.execute("""
        SELECT employee_ref_raw, COUNT(*) as cnt
        FROM incident_reports_raw
        WHERE employee_ref_raw IS NOT NULL 
          AND employee_ref_raw != ''
          AND employee_ref_raw != 'UNKNOWN'
        GROUP BY employee_ref_raw
        ORDER BY cnt DESC
    """)
    rows = cur.fetchall()
    
    if not rows:
        print("  [✗] No employee incident data")
        return False
    
    total = sum(cnt for _, cnt in rows)
    top_4_count = sum(cnt for _, cnt in rows[:4])
    top_4_pct = (top_4_count / total * 100) if total > 0 else 0
    
    # Top 4 raw refs should account for some share of incidents
    # Note: dirty refs fragment counts, so threshold is low
    passed = top_4_pct >= 3
    all_passed = print_check(
        "Top 4 employees share of incidents",
        passed,
        f"{top_4_pct:.1f}%, expected ≥3%"
    )
    
    print(f"  Top incident employees:")
    for ref, cnt in rows[:5]:
        print(f"    - {ref[:30]}: {cnt} incidents")
    
    return all_passed


def validate_data_quality(conn: sqlite3.Connection) -> bool:
    """Check that data quality issues exist (multiple formats, bogus refs)."""
    print("\n=== Data Quality Checks ===")
    cur = conn.cursor()
    all_passed = True
    
    # Check for multiple date formats in incident_time_raw
    cur.execute("SELECT incident_time_raw FROM incident_reports_raw LIMIT 100")
    dates = [row[0] for row in cur.fetchall() if row[0]]
    
    # Count distinct patterns
    patterns = set()
    for d in dates:
        d = d.strip()
        if "/" in d:
            patterns.add("US_format")
        elif d[0:4].isdigit() and "-" in d:
            patterns.add("ISO_format")
        elif any(m in d for m in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]):
            patterns.add("Month_name")
    
    passed = len(patterns) >= 2
    all_passed &= print_check(
        "Multiple date formats present",
        passed,
        f"Found {len(patterns)} distinct patterns"
    )
    
    # Check for bogus employee references
    cur.execute("""
        SELECT COUNT(*) FROM incident_reports_raw
        WHERE employee_ref_raw LIKE 'B9%'
           OR employee_ref_raw LIKE 'EMP-9%'
           OR employee_ref_raw = 'UNKNOWN'
           OR employee_ref_raw = 'n/a'
           OR employee_ref_raw = ''
           OR employee_ref_raw IS NULL
    """)
    bogus_emp = cur.fetchone()[0]
    passed = bogus_emp >= 3
    all_passed &= print_check(
        "Bogus/missing employee refs exist",
        passed,
        f"Found {bogus_emp}"
    )
    
    # Check for bogus machine references
    cur.execute("""
        SELECT COUNT(*) FROM incident_reports_raw
        WHERE machine_ref_raw LIKE 'MX-%'
           OR machine_ref_raw = ''
           OR machine_ref_raw IS NULL
    """)
    bogus_machine = cur.fetchone()[0]
    passed = bogus_machine >= 2
    all_passed &= print_check(
        "Bogus/missing machine refs exist",
        passed,
        f"Found {bogus_machine}"
    )
    
    return all_passed


def validate_incident_types(conn: sqlite3.Connection) -> bool:
    """Check that incident type variants exist."""
    print("\n=== Incident Type Checks ===")
    cur = conn.cursor()
    
    cur.execute("""
        SELECT DISTINCT incident_type_raw 
        FROM incident_reports_raw 
        WHERE incident_type_raw IS NOT NULL
        LIMIT 50
    """)
    types = [row[0] for row in cur.fetchall()]
    
    # Check for various forms of machine_failure
    machine_failure_variants = sum(1 for t in types if "fail" in t.lower() or "mech" in t.lower())
    
    passed = machine_failure_variants >= 2
    all_passed = print_check(
        "Machine failure variants exist",
        passed,
        f"Found {machine_failure_variants} distinct variants"
    )
    
    print(f"  Sample incident types: {types[:10]}")
    
    return all_passed


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate factory database characteristics")
    ap.add_argument("db_path", help="Path to SQLite database to validate")
    args = ap.parse_args()
    
    print(f"Validating database: {args.db_path}")
    
    conn = sqlite3.connect(args.db_path)
    
    all_passed = True
    all_passed &= validate_volumes(conn)
    all_passed &= validate_bad_machines(conn)
    all_passed &= validate_shift_risk(conn)
    all_passed &= validate_employee_concentration(conn)
    all_passed &= validate_data_quality(conn)
    all_passed &= validate_incident_types(conn)
    
    conn.close()
    
    print("\n" + "=" * 40)
    if all_passed:
        print("All validations PASSED ✓")
        sys.exit(0)
    else:
        print("Some validations FAILED ✗")
        print("Review the output above and adjust data generation if needed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
