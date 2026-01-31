# Factory Data Specification

This document defines the data schema, generation rules, and quality characteristics for the factory incident database. Use this as the source of truth if the implementation needs to be rebuilt.

---

## Overview

A SQLite database simulating a manufacturing facility's operations over ~2 years.

| Dimension | Target |
|-----------|--------|
| Employees | ~60 |
| Machines | ~40 |
| Machine Types | 6 |
| Zones | 6 |
| Shifts | ~2,200 (3 per day × ~730 days) |
| Incidents | 400-600 |
| Maintenance Logs | 200-350 |

---

## Schema

### Reference Tables (Clean)

These tables have consistent, well-formatted data with proper constraints.

#### `machine_types`
```sql
CREATE TABLE machine_types (
  machine_type_id INTEGER PRIMARY KEY,
  type_name TEXT NOT NULL UNIQUE,      -- Press, CNC, Conveyor, RobotArm, LaserCutter, Mixer
  category TEXT NOT NULL,               -- forming, machining, material_handling, assembly, cutting, processing
  typical_mtbf_hours INTEGER            -- Mean time between failures (for reference)
);
```

**Seed data:**
| type_name | category | typical_mtbf_hours |
|-----------|----------|-------------------|
| Press | forming | 650 |
| CNC | machining | 900 |
| Conveyor | material_handling | 500 |
| RobotArm | assembly | 1200 |
| LaserCutter | cutting | 800 |
| Mixer | processing | 700 |

#### `incident_types`
```sql
CREATE TABLE incident_types (
  incident_type_id INTEGER PRIMARY KEY,
  incident_type TEXT NOT NULL UNIQUE,   -- Canonical name
  category TEXT NOT NULL,                -- equipment, safety, quality, facility, other
  default_severity TEXT NOT NULL         -- low, medium, high
);
```

**Seed data:**
| incident_type | category | default_severity |
|---------------|----------|------------------|
| machine_failure | equipment | high |
| safety_violation | safety | medium |
| near_miss | safety | low |
| injury_minor | safety | medium |
| injury_major | safety | high |
| quality_defect | quality | low |
| power_event | facility | medium |
| unknown | other | low |

#### `zones`
```sql
CREATE TABLE zones (
  zone_id INTEGER PRIMARY KEY,
  zone_code TEXT NOT NULL UNIQUE,   -- Z-01 through Z-06
  zone_name TEXT NOT NULL
);
```

**Seed data:**
| zone_code | zone_name |
|-----------|-----------|
| Z-01 | Inbound / Receiving |
| Z-02 | Machining Bay |
| Z-03 | Assembly Line |
| Z-04 | Packaging |
| Z-05 | Maintenance Corner |
| Z-06 | Utilities / Power |

---

### Dimension Tables (Clean)

#### `employees`
```sql
CREATE TABLE employees (
  employee_id INTEGER PRIMARY KEY,
  badge_id TEXT NOT NULL UNIQUE,    -- B0001, B0002, ... B0060
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  hire_date TEXT NOT NULL,          -- ISO yyyy-mm-dd
  role TEXT NOT NULL,               -- Operator, Technician, Quality, Maintenance, Supervisor
  status TEXT NOT NULL              -- active, leave, terminated
);
```

**Generation rules:**
- ~60 employees
- Badge IDs: `B0001` through `B0060`
- Names: Random from predefined lists (gender-neutral first names, diverse last names)
- Hire dates: Random within 2018-01-01 to 2024-01-01
- Role distribution: 60% Operator, 15% Technician, 10% Quality, 10% Maintenance, 5% Supervisor
- Status distribution: 92% active, 5% leave, 3% terminated

#### `machines`
```sql
CREATE TABLE machines (
  machine_id INTEGER PRIMARY KEY,
  machine_code TEXT NOT NULL UNIQUE,    -- M-001 through M-040
  machine_type_id INTEGER NOT NULL,
  vendor TEXT NOT NULL,
  install_date TEXT NOT NULL,           -- ISO yyyy-mm-dd
  status TEXT NOT NULL,                 -- active, maintenance, retired
  FOREIGN KEY(machine_type_id) REFERENCES machine_types(machine_type_id)
);
```

**Generation rules:**
- ~40 machines
- Machine codes: `M-001` through `M-040`
- Type distribution: Press and Conveyor more common (weight 3), CNC and LaserCutter medium (weight 2), others lower
- Vendors: Random from list (Apex Industrial, NorthBridge Robotics, CrownWorks, OmniFab, Kinetic Machines, VectorForge)
- Install dates: Random within 2019-01-01 to 2025-01-01
- Status: 90% active, 8% maintenance, 2% retired

---

### Raw Tables (Messy)

These tables simulate real-world data entry with inconsistencies.

#### `layout_raw`
```sql
CREATE TABLE layout_raw (
  layout_id INTEGER PRIMARY KEY,
  machine_ref_raw TEXT NOT NULL,    -- Dirty machine reference
  zone_ref_raw TEXT NOT NULL,       -- Dirty zone reference
  x REAL,
  y REAL,
  row_num INTEGER,
  col_num INTEGER,
  effective_from_raw TEXT NOT NULL  -- Dirty date
);
```

**Generation rules:**
- One row per machine (mostly)
- 3 extra rows referencing non-existent machines (M-999, M-000, MX-404)
- Machine placement by type: Press/CNC/LaserCutter → Z-02/Z-03, Conveyor/RobotArm → Z-03/Z-04, Mixer → Z-01/Z-05
- 5% chance of random zone assignment (simulating outdated records)

#### `shifts_raw`
```sql
CREATE TABLE shifts_raw (
  shift_id INTEGER PRIMARY KEY,
  shift_code TEXT NOT NULL UNIQUE,      -- S-YYYYMMDD-{D|S|N}
  shift_name TEXT NOT NULL,             -- Day, Swing, Night
  shift_start_raw TEXT NOT NULL,        -- Dirty timestamp
  shift_end_raw TEXT NOT NULL,          -- Dirty timestamp
  supervisor_ref_raw TEXT,              -- Dirty employee reference
  team_code TEXT,                       -- A1, B2, C3, D4, etc.
  created_at_iso TEXT NOT NULL          -- Clean ISO timestamp (ingestion time)
);
```

**Shift definitions:**
| Shift | Start | End | Suffix |
|-------|-------|-----|--------|
| Day | 06:00 | 14:00 | D |
| Swing | 14:00 | 22:00 | S |
| Night | 22:00 | 06:00 (+1 day) | N |

**Generation rules:**
- 3 shifts per day for entire date range (default: 2024-01-01 to 2025-12-31)
- Shift code format: `S-20240115-D` (date + shift suffix)
- Timestamps use dirty format (see Date Formats below)

#### `shift_assignments_raw`
```sql
CREATE TABLE shift_assignments_raw (
  assignment_id INTEGER PRIMARY KEY,
  shift_code TEXT NOT NULL,
  employee_ref_raw TEXT NOT NULL,       -- Dirty employee reference
  role_ref_raw TEXT NOT NULL,           -- Dirty role (OPR, Tech, Supv, etc.)
  clock_in_raw TEXT,                    -- Dirty timestamp (may be missing)
  clock_out_raw TEXT,                   -- Dirty timestamp (may be missing)
  created_at_iso TEXT NOT NULL
);
```

**Generation rules:**
- ~18 employees assigned per shift (gaussian, min 8)
- Clock-in: shift_start ± random(-10 to +20 minutes), 4% chance missing/invalid
- Clock-out: shift_end ± random(-20 to +25 minutes), 6% chance missing/invalid

#### `incident_reports_raw`
```sql
CREATE TABLE incident_reports_raw (
  incident_id INTEGER PRIMARY KEY,
  incident_time_raw TEXT NOT NULL,      -- Dirty timestamp
  reported_time_raw TEXT NOT NULL,      -- Dirty timestamp (1-180 min after incident)
  shift_code_ref_raw TEXT,              -- Dirty shift reference (6% chance missing/wrong)
  employee_ref_raw TEXT,                -- Dirty employee reference (4% chance missing)
  machine_ref_raw TEXT,                 -- Dirty machine reference (3% chance missing)
  zone_ref_raw TEXT,                    -- Dirty zone reference (2% chance missing)
  incident_type_raw TEXT NOT NULL,      -- Dirty incident type
  severity_raw TEXT NOT NULL,           -- Dirty severity
  description TEXT,
  created_at_iso TEXT NOT NULL
);
```

#### `maintenance_logs_raw`
```sql
CREATE TABLE maintenance_logs_raw (
  maintenance_id INTEGER PRIMARY KEY,
  machine_ref_raw TEXT NOT NULL,        -- Dirty machine reference
  maint_start_raw TEXT NOT NULL,        -- Dirty timestamp
  maint_end_raw TEXT,                   -- Dirty timestamp (8% chance missing)
  maint_type_raw TEXT NOT NULL,         -- Preventive, PREV, Corrective, CORR, etc.
  notes TEXT,
  created_at_iso TEXT NOT NULL
);
```

**Generation rules:**
- 65% of machine_failure incidents generate a correlated maintenance log
- Maintenance starts 5-120 minutes after incident
- Duration: 15-240 minutes
- Additional ~35 random preventive maintenance logs (not tied to incidents)

---

## Data Quality Issues

### Date/Time Formats

Timestamps are stored as strings in one of these formats (randomly chosen):

| Format | Example |
|--------|---------|
| `%Y-%m-%d %H:%M:%S` | 2024-03-15 14:32:45 |
| `%Y-%m-%d %H:%M` | 2024-03-15 14:32 |
| `%Y-%m-%d %H` | 2024-03-15 14 |
| `%Y-%m-%d` | 2024-03-15 |
| `%m/%d/%Y %H:%M:%S` | 03/15/2024 14:32:45 |
| `%m/%d/%Y %H:%M` | 03/15/2024 14:32 |
| `%m/%d/%Y` | 03/15/2024 |
| `%d-%b-%Y %H:%M:%S` | 15-Mar-2024 14:32:45 |
| `%d-%b-%Y %H:%M` | 15-Mar-2024 14:32 |

**Additional noise:**
- 8% chance of leading/trailing whitespace
- 10% chance of time truncation (drop minutes/seconds)
- 5% chance of dropping time entirely

### Employee Reference Variants

An employee (ID=42, badge=B0042, name="Casey Patel") may appear as:

| Variant | Example |
|---------|---------|
| Badge ID | B0042 |
| Badge lowercase | b0042 |
| EMP-ID format | EMP-42 |
| Just the number | 42 |
| Full name | Casey Patel |
| Name uppercase | CASEY PATEL |
| Badge with spaces | ` B0042 ` |
| Badge: prefix | Badge:B0042 |

**Bogus references (6% chance):**
- Non-existent badge: `B9XXX`
- Non-existent ID: `EMP-9XXX`
- Placeholder: `UNKNOWN`, `n/a`, empty string

### Machine Reference Variants

A machine (code=M-017) may appear as:

| Variant | Example |
|---------|---------|
| Canonical | M-017 |
| Lowercase | m-017 |
| No hyphen | M017 |
| Just digits | 017 |
| "Machine" prefix | Machine 017 |
| M prefix | M17 |
| Extra spaces | ` M-017 ` |
| Wrong prefix (15% chance) | MX-017 |

### Zone Reference Variants

A zone (code=Z-02) may appear as:

| Variant | Example |
|---------|---------|
| Canonical | Z-02 |
| Lowercase | z-02 |
| No hyphen | Z02 |
| "Zone" prefix | Zone Z-02 |
| Extra spaces | ` Z-02 ` |

**Bogus references (3% chance):** `Z-99`, `ZONE-UNKNOWN`, empty string

### Incident Type Variants

Each canonical type has multiple representations:

| Canonical | Variants |
|-----------|----------|
| machine_failure | Machine Failure, machine_fail, MECH_FAIL, Mach failure, `machine failure ` |
| safety_violation | Safety Violation, SAFETY_VIOL, safety-violation, Safety vio. |
| near_miss | Near Miss, near-miss, NEAR_MISS, Nearmiss |
| injury_minor | Minor Injury, injury_minor, MIN_INJ, Minor inj. |
| injury_major | Major Injury, injury_major, MAJ_INJ, Major inj. |
| quality_defect | Quality Defect, quality_defect, QA_DEFECT, Quality issue |
| power_event | Power Event, power_event, PWR_EVT, Power fluctuation |
| unknown | Unknown, UNK, ?, n/a |

### Severity Variants

| Canonical | Variants |
|-----------|----------|
| low | low, LOW, 1, sev1, minor, L |
| medium | medium, MED, 2, sev2, moderate, M |
| high | high, HIGH, 3, sev3, major, H |
| critical | critical, CRIT, 4, sev4, catastrophic, C |

### Role Variants

Roles in `shift_assignments_raw` use inconsistent naming:
- Operator, OPR
- Tech, Technician
- Supervisor, Supv
- Quality, QA
- Maintenance, Maint

### Typos

6% chance of character transposition in incident_type_raw, severity_raw, and maint_type_raw.
Example: "Machine Failure" → "Mahcine Failure"

---

## Outliers (Required)

These patterns MUST be present in the generated data for the exercise to work:

### Bad Machines

Specific machines have 3-4x the normal incident rate:
- **M-003** — forced outlier
- **M-017** — forced outlier
- **M-024** — forced outlier
- Plus 0-2 additional random machines

Implementation: When selecting machine for incident, these get weight multiplier of 4.0

### Machine Type Risk

Some machine types are more prone to incidents:

| Type | Multiplier |
|------|------------|
| Press | 1.9 |
| Conveyor | 1.6 |
| LaserCutter | 1.3 |
| CNC | 1.2 |
| Mixer | 1.1 |
| RobotArm | 1.05 |

### Bad Employees

4 randomly selected employees are 3.5x more likely to appear in incidents.

### Shift Risk

Night shift has significantly higher incident rate:

| Shift | Multiplier |
|-------|------------|
| Day | 1.0 |
| Swing | 1.15 |
| Night | 1.45 |

### Incident Type Distribution by Machine

| Machine Type | Bias |
|--------------|------|
| Press | +15% machine_failure, +5% injury_minor |
| Conveyor | +12% machine_failure, +6% near_miss |
| LaserCutter | +10% quality_defect, +6% safety_violation |

### Severity Distribution by Incident Type

| Incident Type | Severity Distribution |
|---------------|----------------------|
| injury_major | 70% high, 30% critical |
| machine_failure | 55% medium, 45% high |
| safety_violation, power_event | 25% low, 55% medium, 20% high |
| Others | 70% low, 30% medium |

---

## Incident Generation Algorithm

For each shift:

1. Calculate base lambda (expected incidents) = 0.08
2. Apply shift risk multiplier (D=1.0, S=1.15, N=1.45)
3. Count "bad employees" on shift, add 8% per bad employee
4. Generate k incidents using pseudo-Poisson:
   - Roll 4 times, each has `min(0.95, lambda/2)` chance of +1
   - If k=0, 8% × lambda chance of k=1
5. For each incident:
   - Select machine (weighted by type + bad machine status)
   - Select employee (85% from shift team, weighted by bad employee status)
   - Select time randomly within shift window
   - Generate dirty references and type/severity

---

## Validation Checks

After generation, verify:

1. **Volume:**
   - Employees: 55-65
   - Machines: 35-45
   - Shifts: 2000-2400
   - Incidents: 350-650
   - Maintenance logs: 150-400

2. **Outliers:**
   - M-003, M-017, M-024 each have ≥2x average incident rate
   - Night shift incident rate ≥1.3x day shift rate
   - Top 4 employees account for ≥12% of incidents

3. **Data quality:**
   - At least 5 distinct date formats present
   - At least 3 incidents reference non-existent employees
   - At least 3 incidents reference non-existent machines

---

## Append Script Behavior

The append script adds N days of new data starting from the day after the last shift in the database:

1. Find max shift_code, extract date
2. Generate N days of shifts, assignments, incidents, maintenance
3. Use same outlier patterns (bad machines, employees, shift risk)
4. Same dirty data generation rules

This allows testing incremental pipeline updates.
