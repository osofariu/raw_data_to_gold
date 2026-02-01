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

## Step 7: Group Overlapping Windows into Distinct Clusters (Gap-and-Island)

The previous queries count incidents with neighbors, but don't group them into distinct **cluster events**. 

For example, if incidents A, B, C, D happen within a 4-hour window, they form ONE cluster event — but our query shows them as 4 separate rows.

### The Gap-and-Island Approach

1. Order all incidents by time
2. Check if each incident is within 4 hours of the previous one
3. When there's a gap > 4 hours, start a new cluster
4. Assign cluster IDs and aggregate

### Identify Cluster Boundaries

```sql
WITH ordered_incidents AS (
    SELECT 
        incident_id,
        incident_time,
        LAG(incident_time) OVER (ORDER BY incident_time) as prev_time
    FROM incidents_clean
    WHERE incident_time IS NOT NULL
),
with_gaps AS (
    SELECT 
        incident_id,
        incident_time,
        prev_time,
        CASE 
            WHEN prev_time IS NULL THEN 1
            WHEN (julianday(incident_time) - julianday(prev_time)) * 24 > 4 THEN 1
            ELSE 0
        END as is_new_cluster
    FROM ordered_incidents
),
with_cluster_id AS (
    SELECT 
        incident_id,
        incident_time,
        SUM(is_new_cluster) OVER (ORDER BY incident_time) as cluster_id
    FROM with_gaps
)
SELECT cluster_id, incident_id, incident_time
FROM with_cluster_id
ORDER BY incident_time;
```

### Count Distinct Cluster Events (3+ incidents)

```sql
WITH ordered_incidents AS (
    SELECT 
        incident_id,
        incident_time,
        LAG(incident_time) OVER (ORDER BY incident_time) as prev_time
    FROM incidents_clean
    WHERE incident_time IS NOT NULL
),
with_gaps AS (
    SELECT 
        incident_id,
        incident_time,
        CASE 
            WHEN prev_time IS NULL THEN 1
            WHEN (julianday(incident_time) - julianday(prev_time)) * 24 > 4 THEN 1
            ELSE 0
        END as is_new_cluster
    FROM ordered_incidents
),
with_cluster_id AS (
    SELECT 
        incident_id,
        incident_time,
        SUM(is_new_cluster) OVER (ORDER BY incident_time) as cluster_id
    FROM with_gaps
),
cluster_sizes AS (
    SELECT 
        cluster_id,
        COUNT(*) as size,
        MIN(incident_time) as start_time,
        MAX(incident_time) as end_time
    FROM with_cluster_id
    GROUP BY cluster_id
)
SELECT 
    cluster_id,
    size,
    start_time,
    end_time,
    ROUND((julianday(end_time) - julianday(start_time)) * 24, 1) as duration_hours
FROM cluster_sizes
WHERE size >= 3
ORDER BY size DESC;
```

### Summary: How Many Cluster Events?

```sql
WITH ordered_incidents AS (
    SELECT 
        incident_id,
        incident_time,
        LAG(incident_time) OVER (ORDER BY incident_time) as prev_time
    FROM incidents_clean
    WHERE incident_time IS NOT NULL
),
with_gaps AS (
    SELECT 
        incident_id,
        incident_time,
        CASE 
            WHEN prev_time IS NULL THEN 1
            WHEN (julianday(incident_time) - julianday(prev_time)) * 24 > 4 THEN 1
            ELSE 0
        END as is_new_cluster
    FROM ordered_incidents
),
with_cluster_id AS (
    SELECT 
        incident_id,
        incident_time,
        SUM(is_new_cluster) OVER (ORDER BY incident_time) as cluster_id
    FROM with_gaps
),
cluster_sizes AS (
    SELECT cluster_id, COUNT(*) as size
    FROM with_cluster_id
    GROUP BY cluster_id
)
SELECT 
    COUNT(*) as total_cluster_events,
    SUM(CASE WHEN size >= 3 THEN 1 ELSE 0 END) as clusters_3plus,
    SUM(CASE WHEN size >= 5 THEN 1 ELSE 0 END) as clusters_5plus,
    MAX(size) as largest_cluster
FROM cluster_sizes;
```

### Why This Matters

| Metric | Value | Business Meaning |
|--------|-------|------------------|
| Total cluster events | Many | Groups of temporally close incidents |
| Clusters with 3+ | Few | Significant cascading events |
| Largest cluster | ? | Worst day — investigate root cause |

---

## Success Criteria

- [ ] Time parse rate ≥95%
- [ ] Can run time-based clustering query
- [ ] Cluster analysis shows meaningful patterns
- [ ] Can identify distinct cluster events using gap-and-island
