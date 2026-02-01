# Scenario 5: When Do Problems Cluster?

## Goal

Find incident clusters — periods where 3+ incidents occur within a 4-hour window. This helps identify systemic issues that cause cascading problems.

**First task:** Clean the `incident_time_raw` field so we can do time-based analysis.

## The Problem

Before we can analyze time patterns, we need to parse `incident_time_raw` into a consistent datetime format. The raw field contains many variants.

---

## Step 1: Explore the Data

### Sample the raw time values

```sql
SELECT incident_time_raw 
FROM incident_reports_raw 
ORDER BY RANDOM() 
LIMIT 30;
```

### What You'll See

| Format | Example |
|--------|---------|
| ISO date only | `2024-07-05` |
| ISO with time | `2024-07-30 16:17` |
| ISO partial time | `2024-08-02 17` (just hour) |
| DD-Mon-YYYY | `30-Aug-2025 05:19:00` |
| DD-Mon-YYYY partial | `17-Jun-2024 05:44` |
| MM/DD/YYYY | `05/23/2024` |
| MM/DD/YYYY with time | `06/23/2024 01:56:29` |
| Extra whitespace | ` 2025-07-08 ` |

---

## Step 2: Write the Parsing Function

See `pipeline/normalize.py` for `parse_incident_time()`.

The function should:
- Handle all date formats above
- Normalize to ISO format: `YYYY-MM-DD HH:MM:SS`
- Default missing time components to `00:00:00`
- Return `None` for unparseable values

---

## Step 3: Test the Function

```bash
uv run pytest tests/test_normalize.py::TestParseIncidentTime -v
```

---

## Step 4: Build the Clean Table

```bash
uv run python pipeline/build_incidents_clean.py
```

This now creates `incidents_clean` with an `incident_time` column (normalized datetime).

---

## Step 5: Verify Time Parsing

### Check parse rate

```sql
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN incident_time IS NOT NULL THEN 1 ELSE 0 END) as parsed,
    ROUND(100.0 * SUM(CASE WHEN incident_time IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as parse_rate
FROM incidents_clean;
```

### Sample parsed values

```sql
SELECT incident_time_raw, incident_time
FROM incidents_clean
WHERE incident_time IS NOT NULL
LIMIT 20;
```

### What couldn't be parsed?

```sql
SELECT incident_time_raw, COUNT(*) as cnt
FROM incidents_clean
WHERE incident_time IS NULL
GROUP BY incident_time_raw
ORDER BY cnt DESC;
```

---

## Step 6: Find Incident Clusters (First Analysis Task)

Now we can do time-based analysis. Find incidents with 2+ others within ±2 hours:

```sql
WITH incident_with_neighbors AS (
    SELECT 
        a.incident_id,
        a.incident_time,
        COUNT(b.incident_id) as nearby_count
    FROM incidents_clean a
    JOIN incidents_clean b 
        ON b.incident_time BETWEEN 
           datetime(a.incident_time, '-2 hours') 
           AND datetime(a.incident_time, '+2 hours')
        AND a.incident_id != b.incident_id
    WHERE a.incident_time IS NOT NULL
      AND b.incident_time IS NOT NULL
    GROUP BY a.incident_id
)
SELECT * FROM incident_with_neighbors 
WHERE nearby_count >= 2
ORDER BY nearby_count DESC;
```

### How many incidents are part of clusters?

```sql
WITH incident_with_neighbors AS (
    SELECT 
        a.incident_id,
        COUNT(b.incident_id) as nearby_count
    FROM incidents_clean a
    JOIN incidents_clean b 
        ON b.incident_time BETWEEN 
           datetime(a.incident_time, '-2 hours') 
           AND datetime(a.incident_time, '+2 hours')
        AND a.incident_id != b.incident_id
    WHERE a.incident_time IS NOT NULL
      AND b.incident_time IS NOT NULL
    GROUP BY a.incident_id
)
SELECT 
    COUNT(*) as total_incidents,
    SUM(CASE WHEN nearby_count >= 2 THEN 1 ELSE 0 END) as clustered_incidents,
    ROUND(100.0 * SUM(CASE WHEN nearby_count >= 2 THEN 1 ELSE 0 END) / COUNT(*), 1) as cluster_pct
FROM incident_with_neighbors;
```

---

## Success Criteria

- [ ] Time parse rate ≥95%
- [ ] Can run time-based clustering query
- [ ] Cluster analysis shows meaningful patterns
