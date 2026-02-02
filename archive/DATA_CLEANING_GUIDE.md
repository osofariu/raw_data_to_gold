# Data Cleaning Pipeline Guide

A practical guide for building data transformation pipelines that clean messy data while preserving the original source. Based on industry best practices for data engineering.

---

## The Problem

You have a database with messy data:

- Upstream processes write to it and won't change
- You can't modify the raw tables or add constraints
- You need clean, queryable data for analysis

**Solution:** Build a transformation layer that reads from the raw tables and writes to clean tables/views, triggered on demand.

---

## Key Decision: Views vs. Tables

### When to Use Views

| Pros                                         | Cons                                   |
| -------------------------------------------- | -------------------------------------- |
| Always fresh (queries raw data in real-time) | Slower queries (recomputes every time) |
| No storage overhead                          | Can't add indexes                      |
| No sync/refresh needed                       | Complex views become slow              |
| Great for simple transformations             |                                        |

**Best for:** Small datasets, simple transformations, development/prototyping.

```sql
-- Example: A view that normalizes machine references
CREATE VIEW machine_ref_normalized AS
SELECT 
  incident_id,
  machine_ref_raw,
  CASE
    WHEN UPPER(TRIM(machine_ref_raw)) GLOB 'M-[0-9][0-9][0-9]' 
      THEN UPPER(TRIM(machine_ref_raw))
    WHEN UPPER(TRIM(machine_ref_raw)) GLOB 'M[0-9][0-9][0-9]' 
      THEN 'M-' || SUBSTR(UPPER(TRIM(machine_ref_raw)), 2)
    -- ... more patterns
  END AS machine_code_clean
FROM incident_reports_raw;
```

### When to Use Tables

| Pros                        | Cons                     |
| --------------------------- | ------------------------ |
| Fast queries (pre-computed) | Requires refresh process |
| Can add indexes             | Storage overhead         |
| Can track transform history | Can get stale            |
| Handles complex logic well  |                          |

**Best for:** Frequently queried data, complex transformations, production use.

```sql
-- Example: A table populated by a refresh script
CREATE TABLE incidents_clean (
  incident_id INTEGER PRIMARY KEY,
  incident_time DATETIME,          -- Parsed from incident_time_raw
  machine_id INTEGER,              -- Resolved from machine_ref_raw
  employee_id INTEGER,             -- Resolved from employee_ref_raw
  incident_type_id INTEGER,        -- Resolved from incident_type_raw
  severity TEXT,                   -- Normalized
  -- ... metadata
  _raw_machine_ref TEXT,           -- Keep original for debugging
  _matched_by TEXT,                -- How we matched (badge, name, pattern)
  _created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### The Practical Path

**Start with views** during development — they're easy to iterate on. **Convert to tables** when:

- Query performance degrades
- You need indexes
- The transformation logic stabilizes
- You're ready for production

---

## Pipeline Architecture Options

### Option 1: Pure SQL Scripts

The simplest approach. A series of SQL files that run in sequence.

```
pipeline/
├── 01_create_mapping_tables.sql
├── 02_populate_machine_mapping.sql
├── 03_populate_employee_mapping.sql
├── 04_create_incidents_clean.sql
├── 05_refresh_incidents_clean.sql
└── run_pipeline.sh
```

**Pros:** No dependencies, portable, easy to understand.  
**Cons:** No orchestration, manual dependency management.

```bash
#!/bin/bash
# run_pipeline.sh
sqlite3 data/factory_training.db < pipeline/01_create_mapping_tables.sql
sqlite3 data/factory_training.db < pipeline/02_populate_machine_mapping.sql
# ... etc
```

### Option 2: Python with SQL

Python orchestrates, SQL does the heavy lifting.

```python
import sqlite3
from pathlib import Path

def run_pipeline(db_path: str):
    conn = sqlite3.connect(db_path)
    
    # Step 1: Refresh machine mapping
    conn.executescript(Path("sql/machine_mapping.sql").read_text())
    
    # Step 2: Refresh employee mapping (more complex, uses Python)
    refresh_employee_mapping(conn)
    
    # Step 3: Rebuild clean incidents table
    conn.executescript(Path("sql/incidents_clean.sql").read_text())
    
    conn.commit()
    conn.close()
```

**Pros:** Flexibility for complex logic, can use Python libraries.  
**Cons:** More moving parts.

### Option 3: dbt (Data Build Tool)

A popular open-source tool for SQL-based transformations.

```yaml
# dbt_project.yml
name: factory_cleaning
version: '1.0.0'

models:
  factory_cleaning:
    staging:
      +materialized: view      # Quick iteration
    marts:
      +materialized: table     # Production queries
```

```sql
-- models/staging/stg_incidents.sql
SELECT
  incident_id,
  {{ parse_datetime('incident_time_raw') }} as incident_time,
  {{ normalize_machine_ref('machine_ref_raw') }} as machine_code,
  ...
FROM {{ source('raw', 'incident_reports_raw') }}
```

**Pros:** Built-in dependency management, testing, documentation.  
**Cons:** Learning curve, SQLite support is community-maintained.

**Installation:**

```bash
pip install dbt-core dbt-sqlite
```

### Recommendation for This Workshop

**Option 2 (Python + SQL)** strikes the right balance:

- Familiar to developers
- Flexible enough for entity resolution logic
- No extra tools to install (beyond Python + sqlite3)
- Easy to understand and debug

---

## Entity Resolution Strategies

Entity resolution = matching messy string references to canonical records.

### Strategy 1: Pattern Matching (SQL)

Good for: Predictable variations with clear patterns.

```sql
-- Normalize machine references
SELECT 
  machine_ref_raw,
  CASE
    -- Already canonical: M-001
    WHEN UPPER(TRIM(machine_ref_raw)) GLOB 'M-[0-9][0-9][0-9]' 
      THEN UPPER(TRIM(machine_ref_raw))
    
    -- Missing hyphen: M001 → M-001
    WHEN UPPER(TRIM(machine_ref_raw)) GLOB 'M[0-9][0-9][0-9]' 
      THEN 'M-' || SUBSTR(UPPER(TRIM(machine_ref_raw)), 2)
    
    -- Just digits: 001 → M-001
    WHEN TRIM(machine_ref_raw) GLOB '[0-9][0-9][0-9]' 
      THEN 'M-' || TRIM(machine_ref_raw)
    
    -- "Machine 17" → M-017
    WHEN UPPER(TRIM(machine_ref_raw)) LIKE 'MACHINE %' 
      THEN 'M-' || PRINTF('%03d', 
        CAST(SUBSTR(TRIM(machine_ref_raw), 9) AS INTEGER))
    
    ELSE NULL  -- Unmatchable
  END AS machine_code_clean
FROM incident_reports_raw;
```

### Strategy 2: Lookup Tables

Good for: Known variants, manual corrections, audit trail.

```sql
-- Create a mapping table
CREATE TABLE machine_ref_mapping (
  raw_value TEXT PRIMARY KEY,
  machine_code TEXT,
  match_method TEXT,  -- 'pattern', 'manual', 'fuzzy'
  confidence REAL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Populate with discovered mappings
INSERT INTO machine_ref_mapping (raw_value, machine_code, match_method)
SELECT DISTINCT 
  machine_ref_raw,
  -- pattern matching logic here
  'pattern'
FROM incident_reports_raw
WHERE machine_ref_raw IS NOT NULL;

-- Use in queries
SELECT i.*, m.machine_code
FROM incident_reports_raw i
LEFT JOIN machine_ref_mapping m ON i.machine_ref_raw = m.raw_value;
```

### Strategy 3: Fuzzy Matching (Python)

Good for: Name matching, typos, when patterns aren't enough.

```python
from rapidfuzz import fuzz, process

def match_employee(raw_ref: str, employees: list[dict]) -> dict | None:
    """Match a raw employee reference to an employee record."""
    
    raw_ref = raw_ref.strip().upper()
    
    # Try exact badge match first
    for emp in employees:
        if raw_ref == emp['badge_id'].upper():
            return {'employee_id': emp['employee_id'], 'method': 'badge_exact'}
        if raw_ref == f"EMP-{emp['employee_id']}":
            return {'employee_id': emp['employee_id'], 'method': 'emp_id'}
    
    # Try name matching with fuzzy logic
    full_names = {f"{e['first_name']} {e['last_name']}".upper(): e for e in employees}
    match = process.extractOne(raw_ref, full_names.keys(), scorer=fuzz.ratio)
    
    if match and match[1] >= 85:  # 85% similarity threshold
        emp = full_names[match[0]]
        return {'employee_id': emp['employee_id'], 'method': 'fuzzy_name', 
                'score': match[1]}
    
    return None  # Unmatchable
```

### Handling Unmatchable Records

Don't hide failures — track them explicitly:

```sql
-- Add columns to track match status
CREATE TABLE incidents_clean (
  ...
  machine_id INTEGER,           -- NULL if unmatched
  _machine_matched BOOLEAN,     -- Did we find a match?
  _machine_match_method TEXT,   -- How we matched
  _machine_raw TEXT             -- Original value for debugging
);

-- Query to find unmatched records
SELECT machine_ref_raw, COUNT(*) as count
FROM incident_reports_raw i
LEFT JOIN machine_ref_mapping m ON i.machine_ref_raw = m.raw_value
WHERE m.machine_code IS NULL
GROUP BY machine_ref_raw
ORDER BY count DESC;
```

---

## Incremental Updates

When new data arrives, you don't want to rebuild everything.

### Approach 1: Timestamp-Based

Track when records were processed:

```sql
-- Add a processed timestamp to raw table (or a separate tracking table)
ALTER TABLE incident_reports_raw ADD COLUMN _processed_at DATETIME;

-- Process only new records
INSERT INTO incidents_clean (...)
SELECT ...
FROM incident_reports_raw
WHERE _processed_at IS NULL
   OR created_at_iso > (SELECT MAX(_source_created_at) FROM incidents_clean);

-- Mark as processed
UPDATE incident_reports_raw 
SET _processed_at = CURRENT_TIMESTAMP
WHERE _processed_at IS NULL;
```

### Approach 2: ID-Based Watermark

Track the last processed ID:

```python
def get_watermark(conn) -> int:
    """Get the last processed incident ID."""
    result = conn.execute(
        "SELECT MAX(incident_id) FROM incidents_clean"
    ).fetchone()
    return result[0] or 0

def process_new_incidents(conn):
    watermark = get_watermark(conn)
    
    new_incidents = conn.execute("""
        SELECT * FROM incident_reports_raw
        WHERE incident_id > ?
        ORDER BY incident_id
    """, (watermark,)).fetchall()
    
    for incident in new_incidents:
        clean_record = transform_incident(incident)
        insert_clean_incident(conn, clean_record)
```

### Approach 3: Full Rebuild (Simple)

For smaller datasets, just rebuild:

```python
def refresh_clean_table(conn):
    conn.execute("DELETE FROM incidents_clean")
    conn.execute("""
        INSERT INTO incidents_clean (...)
        SELECT ... FROM incident_reports_raw ...
    """)
    conn.commit()
```

**For this workshop:** Full rebuild is fine. The dataset is small (~500 incidents), and simplicity beats optimization.

---

## Testing & Validation

### Match Rate Tracking

Create a validation query to measure success:

```sql
-- Match rate summary
SELECT 
  'machines' as entity,
  COUNT(*) as total_refs,
  SUM(CASE WHEN machine_id IS NOT NULL THEN 1 ELSE 0 END) as matched,
  ROUND(100.0 * SUM(CASE WHEN machine_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as match_pct
FROM incidents_clean

UNION ALL

SELECT 
  'employees',
  COUNT(*),
  SUM(CASE WHEN employee_id IS NOT NULL THEN 1 ELSE 0 END),
  ROUND(100.0 * SUM(CASE WHEN employee_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1)
FROM incidents_clean;
```

**Target match rates:**

- Machines: 95%+ (patterns are predictable)
- Employees: 90%+ (names add complexity)
- Incident types: 98%+ (finite set of variants)

### Spotcheck Validation

Manually verify a sample of matches:

```sql
-- Sample of machine matches to verify
SELECT 
  machine_ref_raw,
  machine_code_clean,
  m.machine_code as verified_code,
  CASE WHEN machine_code_clean = m.machine_code THEN '✓' ELSE '✗' END as valid
FROM machine_ref_normalized n
LEFT JOIN machines m ON n.machine_code_clean = m.machine_code
ORDER BY RANDOM()
LIMIT 20;
```

### Unmatched Analysis

Understand why records don't match:

```sql
-- Top unmatched machine references
SELECT 
  machine_ref_raw,
  COUNT(*) as occurrences
FROM incident_reports_raw i
LEFT JOIN incidents_clean c ON i.incident_id = c.incident_id
WHERE c.machine_id IS NULL
GROUP BY machine_ref_raw
ORDER BY occurrences DESC
LIMIT 10;
```

---

## Recommended Schema Design

For this workshop, use **mapping tables + a clean incidents table**:

```
┌─────────────────────┐     ┌─────────────────────┐
│ incident_reports_raw│     │ employees           │
│ (messy)             │     │ (clean)             │
└──────────┬──────────┘     └──────────┬──────────┘
           │                           │
           ▼                           │
┌─────────────────────┐                │
│ employee_ref_mapping│◄───────────────┘
│ raw_value → emp_id  │
└──────────┬──────────┘
           │
           │  ┌─────────────────────┐
           │  │ machines            │
           │  │ (clean)             │
           │  └──────────┬──────────┘
           │             │
           ▼             ▼
┌─────────────────────────────────────┐
│ incidents_clean                     │
│ - Parsed timestamps                 │
│ - Resolved FKs (machine_id, etc.)   │
│ - Normalized categoricals           │
│ - Audit columns (_matched_by, etc.) │
└─────────────────────────────────────┘
```

**Why this approach:**

1. Mapping tables can be inspected and corrected independently
2. Clean table is fast to query (proper FKs, indexes)
3. Audit columns help debug matching issues
4. Original raw values preserved for traceability

---

## Summary: What a Data Engineer Would Do

1. **Explore first** — Understand the mess before writing transformations
2. **Start with views** — Quick iteration during development
3. **Build mapping tables** — For entity resolution with audit trail
4. **Create clean tables** — Pre-computed for production queries
5. **Track match rates** — Know your data quality
6. **Handle failures explicitly** — Don't hide unmatched records
7. **Keep it simple** — Full rebuild is fine for small data; optimize later

---

## Tools Summary

| Tool                 | Purpose                      | When to Use                   |
| -------------------- | ---------------------------- | ----------------------------- |
| **SQLite**           | Source database              | Always (it's the constraint)  |
| **Python + sqlite3** | Pipeline orchestration       | Recommended for this workshop |
| **pandas**           | Complex transformations      | When SQL gets unwieldy        |
| **rapidfuzz**        | Fuzzy string matching        | For name matching             |
| **dbt-sqlite**       | SQL transformation framework | Larger projects, teams        |
| **DuckDB**           | Analytical queries           | When SQLite is too slow       |

---

## Further Reading

- [dbt Materialization Best Practices](https://docs.getdbt.com/best-practices/materializations/1-guide-overview)
- [Using SQLite in Data Pipelines](https://medium.com/@firmanbrilian/using-sqlite-in-data-pipelines)
- [Practical Entity Resolution (AWS)](https://aws.amazon.com/blogs/architecture/practical-entity-resolution-on-aws/)
- [Python ETL: Incremental Data Load Techniques](https://blog.devgenius.io/python-etl-pipeline-the-incremental-data-load-techniques)
