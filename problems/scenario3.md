# Scenario 3: Which 5 Employees Appear in the Most Incidents?

## Goal

Identify the top 5 employees by incident involvement to understand if certain individuals need additional training or support.

## The Problem

The `employee_ref_raw` field in `incident_reports_raw` is the messiest reference field we've seen. The same employee can appear in many different formats.

---

## Step 1: Explore the Data

### See what's in the employees table (clean)

```sql
-- Employee reference data
SELECT employee_id, badge_id, first_name, last_name 
FROM employees 
LIMIT 10;

-- How many employees?
SELECT COUNT(*) FROM employees;
```

### Explore employee_ref_raw in incidents (messy)

```sql
-- How many distinct employee references?
SELECT COUNT(DISTINCT employee_ref_raw) FROM incident_reports_raw;

-- What do the messy values look like?
SELECT employee_ref_raw, COUNT(*) as cnt
FROM incident_reports_raw
GROUP BY employee_ref_raw
ORDER BY cnt DESC
LIMIT 30;
```

### What You'll See

| Variant Type | Examples |
|--------------|----------|
| Badge ID | `B0017`, `b0017`, ` B0008 ` |
| Badge with prefix | `Badge:B0017` |
| EMP format | `EMP-17`, `EMP17` |
| Just number | `17`, `8` |
| Full name | `Casey Patel`, `CASEY PATEL` |
| Placeholders | `UNKNOWN`, `n/a`, empty |
| Bogus refs | `B9123`, `EMP-9999` |

---

## Step 2: The Normalization Strategy

This requires **multiple matching strategies**:

### Strategy 1: Badge Pattern
Extract badge ID from `B0042`, `b0042`, `Badge:B0042`, ` B0042 `

### Strategy 2: EMP-ID Pattern  
Extract from `EMP-42`, `EMP42` → look up badge_id from employee_id

### Strategy 3: Bare Number
`42` could be employee_id (1-60 range) → look up badge_id

### Strategy 4: Name Matching
`Casey Patel`, `CASEY PATEL` → look up badge_id by full name

### Implementation

See `pipeline/normalize.py` for `create_employee_normalizer(employees)`.

Unlike machine/shift normalization, employee normalization needs access to the employees table for lookups. The factory function takes the employee list and returns a normalizer function with the lookup data captured via closure.

---

## Step 3: Test the Function

```bash
uv run pytest tests/test_normalize.py::TestNormalizeEmployeeRef -v
```

---

## Step 4: Create the Views and Tables

```bash
uv run python pipeline/run_scenario3.py
```

This creates:
- `v_incidents_with_employee` — normalizes employee_ref_raw to badge_id
- `incidents_with_employee` — materialized table for querying

---

## Step 5: Answer the Question

### Match Rate Check

```sql
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN badge_id IS NOT NULL THEN 1 ELSE 0 END) as matched,
    ROUND(100.0 * SUM(CASE WHEN badge_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as match_rate
FROM incidents_with_employee;
```

### Top 5 Employees by Incident Count

```sql
SELECT 
    i.badge_id,
    e.first_name || ' ' || e.last_name as full_name,
    COUNT(*) as incident_count
FROM incidents_with_employee i
JOIN employees e ON i.badge_id = e.badge_id
WHERE i.badge_id IS NOT NULL
GROUP BY i.badge_id
ORDER BY incident_count DESC
LIMIT 5;
```

### What Couldn't Be Matched?

```sql
SELECT employee_ref_raw, COUNT(*) as cnt
FROM incidents_with_employee
WHERE badge_id IS NULL
GROUP BY employee_ref_raw
ORDER BY cnt DESC;
```

---

## Step 6: Discussion

### Why Some Refs Can't Be Matched

1. **Bogus badge IDs** — `B9123` doesn't exist in employees table
2. **Bogus employee IDs** — `EMP-9999` is out of range
3. **Empty/placeholder** — No information provided
4. **Typos in names** — Would require fuzzy matching with threshold

### Improving Match Rate

Options for the remaining unmatched:
1. **Lower fuzzy threshold** — Risk of false matches
2. **Lookup table for known typos** — Manual curation
3. **Flag for human review** — Best for important records

---

## Success Criteria

- [ ] Match rate ≥90%
- [ ] Top 5 employees identified
- [ ] Multiple matching strategies working (badge, EMP-ID, name)
- [ ] Unmatched records documented
