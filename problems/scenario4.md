# Scenario 4: Which Machine Type Has the Highest Failure Rate?

## Goal

Calculate the failure rate per machine type to identify which equipment categories need the most attention.

Key insight: **Failure rate** should be failures per machine of that type, not just total failures. A type with more machines will naturally have more incidents.

## The Problem

This scenario requires **chaining multiple normalizations**:
1. Normalize `incident_type_raw` to identify machine failures
2. Normalize `machine_ref_raw` to match to actual machines (reuse existing function)
3. Join through `machines` → `machine_types`
4. Calculate rate

---

## Step 1: Explore the Data

### Canonical incident types

```sql
SELECT incident_type FROM incident_types ORDER BY incident_type;
```

### Explore incident_type_raw variants

```sql
SELECT incident_type_raw, COUNT(*) as cnt
FROM incident_reports_raw
GROUP BY incident_type_raw
ORDER BY cnt DESC
LIMIT 30;
```

### What You'll See

Machine failure appears as many variants:

| Variant | Count |
|---------|-------|
| `Machine Failure` | 41 |
| `Mach failure` | 40 |
| `MECH_FAIL` | 36 |
| `machine failure ` | 31 |
| `machine_fail` | 30 |
| Typos: `Mahcine Failure`, `MachineF ailure` | 2 each |

### Machine counts by type (for rate calculation)

```sql
SELECT mt.type_name, COUNT(*) as machine_count
FROM machines m
JOIN machine_types mt ON m.machine_type_id = mt.machine_type_id
GROUP BY mt.type_name
ORDER BY machine_count DESC;
```

---

## Step 2: Write the Normalization Function

See `pipeline/normalize.py` for `normalize_incident_type()`.

The function maps all variants to canonical types:
- `Machine Failure`, `MECH_FAIL`, `machine_fail` → `machine_failure`
- `Near Miss`, `NEAR_MISS`, `Nearmiss` → `near_miss`
- etc.

---

## Step 3: Test the Function

```bash
uv run pytest tests/test_normalize.py::TestNormalizeIncidentType -v
```

---

## Step 4: Create the Views and Tables

```bash
uv run python pipeline/run_scenario4.py
```

This creates:
- `v_incidents_full` — normalizes both incident_type and machine_ref
- `incidents_full` — materialized table for querying

---

## Step 5: Answer the Question

### Count Machine Failures by Type (Raw Count)

```sql
SELECT 
    mt.type_name,
    COUNT(*) as failure_count
FROM incidents_full i
JOIN machines m ON i.machine_code = m.machine_code
JOIN machine_types mt ON m.machine_type_id = mt.machine_type_id
WHERE i.incident_type = 'machine_failure'
GROUP BY mt.type_name
ORDER BY failure_count DESC;
```

### Failure RATE by Machine Type (Per Machine)

```sql
WITH machine_counts AS (
    SELECT 
        mt.type_name,
        COUNT(*) as total_machines
    FROM machines m
    JOIN machine_types mt ON m.machine_type_id = mt.machine_type_id
    GROUP BY mt.type_name
),
failure_counts AS (
    SELECT 
        mt.type_name,
        COUNT(*) as failures
    FROM incidents_full i
    JOIN machines m ON i.machine_code = m.machine_code
    JOIN machine_types mt ON m.machine_type_id = mt.machine_type_id
    WHERE i.incident_type = 'machine_failure'
    GROUP BY mt.type_name
)
SELECT 
    mc.type_name,
    mc.total_machines,
    COALESCE(fc.failures, 0) as failures,
    ROUND(1.0 * COALESCE(fc.failures, 0) / mc.total_machines, 2) as failures_per_machine
FROM machine_counts mc
LEFT JOIN failure_counts fc ON mc.type_name = fc.type_name
ORDER BY failures_per_machine DESC;
```

**Expected Result:** Press and Conveyor should have higher failure rates than RobotArm or Mixer.

### Incident Type Match Rate

```sql
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN incident_type IS NOT NULL THEN 1 ELSE 0 END) as matched,
    ROUND(100.0 * SUM(CASE WHEN incident_type IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as match_rate
FROM incidents_full;
```

---

## Step 6: Discussion

### Why Rate Matters

If Press has 50 failures and RobotArm has 20, it might look like Press is worse. But if there are 9 Press machines and only 4 RobotArms:
- Press rate: 50/9 = 5.6 failures per machine
- RobotArm rate: 20/4 = 5.0 failures per machine

The rates are actually similar! Raw counts can be misleading.

---

## Success Criteria

- [ ] Incident type match rate ≥98%
- [ ] Failure rate calculated correctly per machine type
- [ ] Press/Conveyor show higher rates than RobotArm/Mixer
