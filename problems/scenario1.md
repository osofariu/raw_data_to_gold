# Scenario 1: Which 3 Machines Have the Most Incidents?

## Goal

Identify the top 3 machines by incident count to prioritize maintenance efforts.

## The Problem

The `machine_ref_raw` field in `incident_reports_raw` contains inconsistent references to machines. We need to normalize these to match the canonical `machine_code` format in the `machines` table.

---

## Step 1: Explore the Data

Run these SQL queries to understand the mess:

```sql
-- How many distinct machine references are there?
SELECT COUNT(DISTINCT machine_ref_raw) as distinct_refs
FROM incident_reports_raw;

-- What do the raw values look like? (sample of most common)
SELECT machine_ref_raw, COUNT(*) as cnt
FROM incident_reports_raw
GROUP BY machine_ref_raw
ORDER BY cnt DESC
LIMIT 20;

-- What do valid machine codes look like?
SELECT machine_code FROM machines ORDER BY machine_code LIMIT 10;
```

### What You'll See

The same machine appears in many forms:

| Variant | Example |
|---------|---------|
| Canonical | `M-017` |
| Lowercase | `m-017` |
| No hyphen | `M017` |
| Just digits | `017`, `17` |
| Verbose | `Machine 017` |
| Extra spaces | ` M-017 ` |
| Typos | `MX-017` |
| Missing | `""`, `NULL` |

---

## Step 2: Write the Normalization Function

See `pipeline/normalize.py` for the `normalize_machine_ref()` function.

The function should:
- Handle all the variants above
- Return canonical format `M-XXX` (e.g., `M-017`)
- Return `None` for unmatchable values

---

## Step 3: Test the Function

Run the tests to verify the function handles all known patterns:

```bash
pytest tests/test_normalize.py -v
```

---

## Step 4: Create the Normalized Tables

Run the pipeline script to create the cleaned tables:

```bash
uv run python pipeline/run_scenario1.py
```

This creates:
1. `incidents_normalized` — normalizes `machine_ref_raw` → `machine_code`
2. `incidents_resolved` — joins to get `machine_id`

> **Why tables, not views?** The normalization uses a Python function registered with SQLite. Tables persist the results so you can query them from any SQL tool.

---

## Step 5: Validate and Answer the Question

Now run these SQL queries to validate and get the answer.

### Check the Match Rate

```sql
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN machine_code IS NOT NULL THEN 1 ELSE 0 END) as matched,
    ROUND(100.0 * SUM(CASE WHEN machine_code IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as match_rate
FROM incidents_normalized;
```

**Expected:** Match rate ≥95%

### Answer: Top 3 Machines with Most Incidents

```sql
SELECT machine_code, COUNT(*) as incident_count
FROM incidents_normalized
WHERE machine_code IS NOT NULL
GROUP BY machine_code
ORDER BY incident_count DESC
LIMIT 3;
```

**Expected:** M-017, M-024, M-003

### What Couldn't Be Matched?

```sql
SELECT machine_ref_raw, COUNT(*) as cnt
FROM incidents_normalized
WHERE machine_code IS NULL
GROUP BY machine_ref_raw
ORDER BY cnt DESC;
```

---

## Step 6: Discussion — Handling Unmatched Records

Some records can't be normalized. In a real situation, you might:

1. **Add to a lookup table** — If `MX-404` is a known typo for `M-040`, add an explicit mapping
2. **Flag for manual review** — Create a report for operations to investigate
3. **Accept the gap** — Some records genuinely have no machine (e.g., facility-wide incidents)
4. **Improve data entry** — Work with upstream to add validation at input time

---

## Success Criteria

- [ ] Match rate ≥95%
- [ ] Top 3 machines identified correctly (M-017, M-024, M-003)
- [ ] Unmatched records documented and discussed
