# Scenario 2: Is the Night Shift Really More Dangerous?

## Goal

Calculate the incident **rate** per shift type (Day/Swing/Night) to determine if night shifts are more dangerous.

Key insight: We need a **rate** (incidents per shift), not just a count. Night has more incidents partly because there are more night shifts — we need to normalize by shift count.

## The Problem

The `shift_code_ref_raw` field in `incident_reports_raw` needs to be normalized to join with `shifts_raw`.

---

## Step 1: Explore the Data

### Check shift_code format in shifts_raw (clean)

```sql
-- Canonical shift_code format
SELECT shift_code, shift_name 
FROM shifts_raw 
LIMIT 10;

-- How many shifts of each type?
SELECT shift_name, COUNT(*) as shift_count
FROM shifts_raw
GROUP BY shift_name;
```

### Explore shift_code_ref_raw in incidents (messy)

```sql
-- How many distinct shift references?
SELECT COUNT(DISTINCT shift_code_ref_raw) as distinct_refs
FROM incident_reports_raw;

-- What do the messy values look like?
SELECT shift_code_ref_raw, COUNT(*) as cnt
FROM incident_reports_raw
GROUP BY shift_code_ref_raw
ORDER BY cnt DESC
LIMIT 20;
```

### What You'll See

| Variant | Example |
|---------|---------|
| Canonical | `S-20240421-N` |
| Extra spaces | ` S-20240831-D ` |
| Lowercase | `s-20240220-d` |
| Missing | `""`, `NULL` |
| Placeholder | `n/a` |

---

## Step 2: Write the Normalization Function

See `pipeline/normalize.py` for the `normalize_shift_code()` function.

The function should:
- Trim whitespace
- Uppercase the value
- Return `None` for empty/placeholder values
- Validate the format matches `S-YYYYMMDD-{D|S|N}`

---

## Step 3: Test the Function

```bash
uv run pytest tests/test_normalize.py::TestNormalizeShiftCode -v
```

---

## Step 4: Create the Views and Tables

```bash
uv run python pipeline/run_scenario2.py
```

This creates:
- `v_incidents_with_shift` — joins incidents to shifts via normalized shift_code
- `incidents_with_shift` — materialized table for querying

---

## Step 5: Answer the Question

### Incident Count by Shift Type (Raw)

```sql
SELECT 
    s.shift_name,
    COUNT(*) as incident_count
FROM incidents_with_shift i
JOIN shifts_raw s ON i.shift_code = s.shift_code
GROUP BY s.shift_name
ORDER BY incident_count DESC;
```

### Incident RATE by Shift Type (Normalized)

```sql
WITH shift_counts AS (
    SELECT shift_name, COUNT(*) as total_shifts
    FROM shifts_raw
    GROUP BY shift_name
),
incident_counts AS (
    SELECT 
        s.shift_name,
        COUNT(*) as total_incidents
    FROM incidents_with_shift i
    JOIN shifts_raw s ON i.shift_code = s.shift_code
    GROUP BY s.shift_name
)
SELECT 
    sc.shift_name,
    sc.total_shifts,
    COALESCE(ic.total_incidents, 0) as total_incidents,
    ROUND(1.0 * COALESCE(ic.total_incidents, 0) / sc.total_shifts, 3) as incidents_per_shift
FROM shift_counts sc
LEFT JOIN incident_counts ic ON sc.shift_name = ic.shift_name
ORDER BY incidents_per_shift DESC;
```

**Expected Result:** Night shift should have ~1.3-1.5x the incident rate of Day shift.

### Check Unmatched Incidents

```sql
SELECT shift_code_ref_raw, COUNT(*) as cnt
FROM incidents_with_shift
WHERE shift_code IS NULL
GROUP BY shift_code_ref_raw
ORDER BY cnt DESC;
```

---

## Step 6: Discussion

### Why Rate Matters

If we only counted incidents:
- Night: 180 incidents
- Day: 120 incidents

We might conclude Night is 1.5x more dangerous. But if there are more Night shifts, that's misleading.

The **rate** (incidents per shift) gives the true comparison.

### Handling Unmatched Records

Some incidents don't have a valid shift reference. Options:
1. Exclude them from rate calculation (what we do)
2. Try to infer shift from incident_time_raw
3. Flag for investigation

---

## Success Criteria

- [ ] Match rate ≥90% for shift_code_ref_raw
- [ ] Incident rate calculated correctly per shift type
- [ ] Night shift shows higher rate than Day (~1.3-1.5x)
