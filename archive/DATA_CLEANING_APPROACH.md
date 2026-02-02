# Data Cleaning Pipeline: Approach & Best Practices

This document outlines the strategies and tools a data engineer would use to build a transformation layer on top of messy source data, while preserving the original schema.

---

## Our Chosen Approach (TL;DR)

| Decision                | Choice                           | Why                                                                  |
| ----------------------- | -------------------------------- | -------------------------------------------------------------------- |
| **Pipeline Pattern**    | Python + SQL                     | Familiar to developers, flexible for complex logic, no extra tooling |
| **Schema Design**       | Layered Views                    | Clear lineage, easy to debug, matches dbt mental model               |
| **Incremental Updates** | Full Rebuild                     | Simple, always consistent; optimize later if needed                  |
| **Entity Resolution**   | Python functions + lookup tables | Best of both: programmatic logic with explicit edge case handling    |

---

## Context & Constraints

| Constraint                        | Implication                                                         |
| --------------------------------- | ------------------------------------------------------------------- |
| Original schema must be preserved | Upstream processes write to raw tables; we can't modify them        |
| Batch pipeline (not real-time)    | Triggered refresh is acceptable; no streaming infrastructure needed |
| Open-source, developer-friendly   | SQL + Python; no enterprise BI tools                                |
| SQLite as source                  | Lightweight, file-based; some limitations on concurrent writes      |

---

## 1. Views vs. Materialized Tables

### When to Use Views

Views are best for:

- **Staging/intermediate transformations** that feed into other models
- **Small datasets** with simple logic requiring real-time freshness
- **Development/exploration** — easy to iterate without rebuilding

**Advantages:**

- Always return fresh data (no staleness)
- No storage overhead
- Simple to create and modify

**Disadvantages:**

- Query performance degrades as logic complexity increases
- Computed on every query (no caching)
- Complex joins can become slow

### When to Use Tables

Separate "clean" tables are best for:

- **End-user facing queries** (dashboards, reports, API responses)
- **Compute-intensive transformations** (complex joins, aggregations)
- **Frequently accessed data** where query speed matters

**Advantages:**

- Fast queries (data is pre-computed)
- Can add indexes for further optimization
- Stable for downstream consumers

**Disadvantages:**

- Requires refresh process to stay current
- Storage overhead
- Risk of stale data if pipeline fails

### Recommendation for This Workshop

**Start with views for development**, then convert to tables when:

- Queries are noticeably slow
- You need to add indexes
- You want a clear separation between "raw" and "clean" layers

For our scenarios, views are likely sufficient given the data volume (~500 incidents).

---

## 2. Pipeline Patterns

We evaluated four approaches and chose **Option B: Python + SQL**.

### Option A: Pure SQL Scripts

**How it works:** A series of `.sql` files executed in order.

```bash
sqlite3 factory.db < 01_create_views.sql
sqlite3 factory.db < 02_create_clean_tables.sql
sqlite3 factory.db < 03_refresh_data.sql
```

**Pros:** Simple, no dependencies, easy to understand  
**Cons:** No dependency management, manual ordering, limited testing

**Why not:** Too limited for entity resolution logic (regex, fuzzy matching).

### Option B: Python + SQL (pandas/SQLAlchemy) ✅ CHOSEN

**How it works:** Python orchestrates the flow; SQL or pandas handles transformations.

```python
import sqlite3
import pandas as pd

def extract():
    conn = sqlite3.connect('factory.db')
    return pd.read_sql('SELECT * FROM incident_reports_raw', conn)

def transform(df):
    df['machine_code'] = df['machine_ref_raw'].apply(normalize_machine_ref)
    df['incident_time'] = pd.to_datetime(df['incident_time_raw'], errors='coerce')
    return df

def load(df):
    conn = sqlite3.connect('factory.db')
    df.to_sql('incidents_clean', conn, if_exists='replace', index=False)
```

**Why we chose this:**

- **Familiar to developers** — no new tools to learn
- **Flexible** — Python handles complex parsing, SQL handles joins
- **Transparent** — logic is visible and debuggable
- **No extra infrastructure** — just Python and SQLite

### Option C: dbt (Data Build Tool)

**How it works:** SQL-based transformation framework with dependency management, testing, and documentation built in.

```sql
-- models/staging/stg_incidents.sql
{{ config(materialized='view') }}

SELECT
    incident_id,
    TRIM(UPPER(machine_ref_raw)) as machine_ref_normalized,
    ...
FROM {{ source('raw', 'incident_reports_raw') }}
```

**Pros:**

- Automatic dependency resolution via `ref()` function
- Built-in testing (`unique`, `not_null`, custom tests)
- Version control friendly
- Industry standard for analytics engineering

**Why not for this workshop:** Learning curve, overkill for our scale, SQLite adapter is community-maintained. However, dbt is the logical **next step for production** use cases.

### Option D: Lightweight Orchestrators (Prefect, Luigi)

**How it works:** Python workflow framework with scheduling, retries, and observability.

```python
from prefect import flow, task

@task
def extract_incidents():
    ...

@task  
def transform_incidents(raw_data):
    ...

@flow
def incident_pipeline():
    raw = extract_incidents()
    clean = transform_incidents(raw)
    load_incidents(clean)
```

**Pros:** Production features (retries, logging, scheduling)  
**Cons:** Additional infrastructure, more setup

**Why not for this workshop:** Adds complexity without teaching value for our scenarios. Good for production systems that need reliability and monitoring.

---

## 3. Entity Resolution Strategies

Entity resolution is matching messy references to canonical records. Here are the strategies, from simplest to most sophisticated:

### Strategy 1: Pattern Matching with SQL

Use `CASE`, `LIKE`, and string functions to normalize common patterns.

```sql
-- Normalize machine references
SELECT 
    machine_ref_raw,
    CASE
        -- Extract digits and format as M-XXX
        WHEN machine_ref_raw GLOB '*[0-9][0-9][0-9]*' THEN
            'M-' || SUBSTR('000' || CAST(
                CAST(REPLACE(REPLACE(REPLACE(UPPER(TRIM(machine_ref_raw)), 
                    'MACHINE ', ''), 'M-', ''), 'M', '') AS INTEGER
            ) AS TEXT), -3)
        ELSE NULL
    END as machine_code_resolved
FROM incident_reports_raw
```

**Pros:** Pure SQL, no external dependencies  
**Cons:** Complex regex, hard to maintain, limited flexibility

### Strategy 2: Lookup Tables (Variant Mapping)

Create explicit mapping tables for known variants.

```sql
CREATE TABLE machine_ref_variants (
    variant TEXT PRIMARY KEY,
    machine_code TEXT NOT NULL
);

INSERT INTO machine_ref_variants VALUES 
    ('M-017', 'M-017'),
    ('m-017', 'M-017'),
    ('M017', 'M-017'),
    ('Machine 17', 'M-017'),
    ('017', 'M-017');
```

Then join:

```sql
SELECT i.*, v.machine_code
FROM incident_reports_raw i
LEFT JOIN machine_ref_variants v 
    ON UPPER(TRIM(i.machine_ref_raw)) = UPPER(v.variant)
```

**Pros:** Explicit, auditable, handles edge cases  
**Cons:** Requires populating the mapping table, maintenance burden

### Strategy 3: Normalization Functions (Python)

Write Python functions that handle the parsing logic.

```python
import re

def normalize_machine_ref(raw: str) -> str | None:
    if not raw or raw.strip() in ('', 'n/a', 'UNKNOWN'):
        return None
    
    # Clean and uppercase
    cleaned = raw.strip().upper()
    
    # Extract numeric portion
    match = re.search(r'(\d{1,3})', cleaned)
    if match:
        num = int(match.group(1))
        if 1 <= num <= 40:  # Valid machine range
            return f'M-{num:03d}'
    
    return None  # Unmatchable
```

**Pros:** Full programming power, readable logic, testable  
**Cons:** Requires Python layer, can't use in pure SQL queries

### Strategy 4: Fuzzy Matching

For name-based matching (like employee names), use similarity algorithms.

```python
from difflib import SequenceMatcher

def fuzzy_match_employee(raw_name: str, employees: list[dict]) -> int | None:
    """Return employee_id if confident match found."""
    best_match = None
    best_score = 0
    
    for emp in employees:
        full_name = f"{emp['first_name']} {emp['last_name']}"
        score = SequenceMatcher(None, raw_name.upper(), full_name.upper()).ratio()
        if score > best_score:
            best_score = score
            best_match = emp['employee_id']
    
    return best_match if best_score > 0.85 else None
```

**Pros:** Handles typos and variations  
**Cons:** Can produce false matches, computationally expensive, needs threshold tuning

### Handling Unmatchable Records

Always track what couldn't be resolved:

```python
def resolve_with_tracking(raw_values, resolver_func):
    resolved = []
    unresolved = []
    
    for raw in raw_values:
        result = resolver_func(raw)
        if result:
            resolved.append((raw, result))
        else:
            unresolved.append(raw)
    
    match_rate = len(resolved) / len(raw_values) * 100
    print(f"Match rate: {match_rate:.1f}% ({len(unresolved)} unresolved)")
    
    return resolved, unresolved
```

### Recommended Strategy

**Scenario 1 & 3 (machines, employees):** Use Strategy 3 (Python normalization functions) for the main logic, with Strategy 2 (lookup tables) for edge cases.

**Demonstrate the thought process:**

1. Start by exploring distinct values
2. Identify patterns
3. Write normalization logic
4. Check match rate
5. Handle edge cases

---

## 4. Schema Design Options

We evaluated three approaches and chose **Option C: Layered Views**.

### Option A: One Big Clean Table

Create a single `incidents_clean` table with all foreign keys resolved.

```sql
CREATE TABLE incidents_clean (
    incident_id INTEGER PRIMARY KEY,
    incident_time DATETIME,
    shift_id INTEGER,
    employee_id INTEGER,
    machine_id INTEGER,
    zone_id INTEGER,
    incident_type_id INTEGER,
    severity TEXT,
    description TEXT,
    -- Audit columns
    _raw_machine_ref TEXT,
    _raw_employee_ref TEXT,
    _match_quality TEXT  -- 'exact', 'fuzzy', 'unresolved'
);
```

**Pros:** Simple to query, all resolution done upfront  
**Cons:** Must rebuild entire table on schema changes

**Why not:** Hard to debug — you can't see intermediate steps.

### Option B: Separate Mapping Tables

Create mapping tables that join at query time.

```sql
CREATE TABLE incident_machine_map (
    incident_id INTEGER PRIMARY KEY,
    machine_ref_raw TEXT,
    machine_id INTEGER,
    match_method TEXT
);

CREATE TABLE incident_employee_map (
    incident_id INTEGER PRIMARY KEY,
    employee_ref_raw TEXT,
    employee_id INTEGER,
    match_method TEXT
);
```

**Pros:** Modular, can update one mapping without touching others  
**Cons:** More joins at query time, more tables to manage

**Why not:** Too many moving parts for a teaching context.

### Option C: Layered Views ✅ CHOSEN

Layer views on top of each other, building complexity incrementally.

```sql
-- Layer 1: Normalize individual fields
CREATE VIEW v_incidents_normalized AS
SELECT 
    incident_id,
    normalize_machine_ref(machine_ref_raw) as machine_code,
    normalize_employee_ref(employee_ref_raw) as badge_id,
    ...
FROM incident_reports_raw;

-- Layer 2: Resolve to foreign keys  
CREATE VIEW v_incidents_resolved AS
SELECT 
    n.*,
    m.machine_id,
    e.employee_id
FROM v_incidents_normalized n
LEFT JOIN machines m ON n.machine_code = m.machine_code
LEFT JOIN employees e ON n.badge_id = e.badge_id;

-- Layer 3: Final clean view with all joins
CREATE VIEW incidents_clean AS
SELECT 
    r.incident_id,
    r.machine_id,
    r.employee_id,
    mt.type_name as machine_type,
    ...
FROM v_incidents_resolved r
LEFT JOIN machines m ON r.machine_id = m.machine_id
LEFT JOIN machine_types mt ON m.machine_type_id = mt.machine_type_id;
```

**Why we chose this:**

- **Clear lineage** — each layer does one thing
- **Easy to debug** — query any layer to see intermediate results
- **DRY** — normalization logic defined once, reused everywhere
- **Matches dbt mental model** — prepares learners for production tools

**Trade-off:** SQLite doesn't cache view results, so complex views recompute on every query. For production with large data, materialize the final layer as a table.

---

## 5. Incremental Updates

When new data arrives, we need to refresh the clean layer. We chose **Full Rebuild**.

### Full Rebuild ✅ CHOSEN

Delete and recreate the clean table from scratch.

```sql
DROP TABLE IF EXISTS incidents_clean;
CREATE TABLE incidents_clean AS SELECT ... FROM v_incidents_resolved;
```

**Why we chose this:**

- **Simple** — one command, no state to track
- **Always consistent** — no risk of partial updates or missed records
- **Good enough for our scale** — ~500 incidents rebuild in milliseconds

**Trade-off:** For large datasets (millions of rows), this becomes slow and wasteful.

### Incremental Merge (Future Optimization)

Only process new/changed records. Use when full rebuild becomes too slow.

```sql
-- Find new records (using created_at_iso as watermark)
INSERT INTO incidents_clean
SELECT * FROM v_incidents_resolved
WHERE created_at_iso > (SELECT MAX(created_at_iso) FROM incidents_clean);
```

For updates (if records can change):

```sql
-- Using SQLite's INSERT OR REPLACE
INSERT OR REPLACE INTO incidents_clean
SELECT * FROM v_incidents_resolved
WHERE created_at_iso > @last_run_time;
```

**dbt approach** (for reference):

```sql
{{ config(
    materialized='incremental',
    unique_key='incident_id'
) }}

SELECT * FROM {{ ref('stg_incidents') }}
{% if is_incremental() %}
WHERE created_at_iso > (SELECT MAX(created_at_iso) FROM {{ this }})
{% endif %}
```

**When to switch:** If pipeline runtime exceeds a few seconds, or if you're processing streaming data.

---

## 6. Testing & Validation

### What to Test

| Test Type                 | Example                                           | Tool                     |
| ------------------------- | ------------------------------------------------- | ------------------------ |
| **Not null**              | `machine_id IS NOT NULL` for resolved records     | SQL assertion            |
| **Uniqueness**            | No duplicate `incident_id` in clean table         | SQL `GROUP BY`           |
| **Referential integrity** | All `machine_id` values exist in `machines`       | SQL `LEFT JOIN` check    |
| **Match rate**            | ≥95% of incidents resolve to valid machine        | Python script            |
| **Value ranges**          | Severity in ('low', 'medium', 'high', 'critical') | SQL `CHECK` or assertion |

### Match Rate Tracking

```python
def calculate_match_rates(conn):
    """Report resolution success rates."""
    
    query = """
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN machine_id IS NOT NULL THEN 1 ELSE 0 END) as machines_matched,
        SUM(CASE WHEN employee_id IS NOT NULL THEN 1 ELSE 0 END) as employees_matched,
        SUM(CASE WHEN incident_type_id IS NOT NULL THEN 1 ELSE 0 END) as types_matched
    FROM incidents_clean
    """
    
    result = conn.execute(query).fetchone()
    
    print(f"Machine match rate:  {result[1]/result[0]*100:.1f}%")
    print(f"Employee match rate: {result[2]/result[0]*100:.1f}%")
    print(f"Type match rate:     {result[3]/result[0]*100:.1f}%")
```

### Unresolved Record Report

```sql
-- Find unresolved machine references
SELECT machine_ref_raw, COUNT(*) as occurrences
FROM incident_reports_raw
WHERE machine_ref_raw NOT IN (
    SELECT machine_ref_raw 
    FROM incidents_clean 
    WHERE machine_id IS NOT NULL
)
GROUP BY machine_ref_raw
ORDER BY occurrences DESC;
```

### Target Match Rates

| Field         | Target | Notes                                     |
| ------------- | ------ | ----------------------------------------- |
| Machine       | ≥95%   | Few variants, mostly pattern-based        |
| Employee      | ≥90%   | More variants, some fuzzy matching needed |
| Incident Type | ≥98%   | Limited vocabulary, mostly exact matches  |
| Zone          | ≥95%   | Simple patterns                           |

Records that can't be matched should be tracked, not discarded. Include them in the clean table with `NULL` foreign keys so they're still queryable.

---

## Summary: Our Approach

### Decisions Made

| Area              | Choice           | Rationale                            |
| ----------------- | ---------------- | ------------------------------------ |
| Pipeline          | Python + SQL     | Familiar, flexible, no extra tooling |
| Schema            | Layered views    | Clear lineage, easy debugging        |
| Updates           | Full rebuild     | Simple, consistent, fast enough      |
| Entity resolution | Python functions | Full programming power for parsing   |

### Tools

- **SQLite** — Source and destination (same database)
- **Python 3.10+** — Orchestration and normalization logic
- **SQL views** — Layered transformation (v_normalized → v_resolved → clean)
- **pandas** (optional) — For exploration and visualization

### Workflow Pattern

1. **Explore** — Examine distinct values in messy fields
2. **Normalize** — Write Python functions that standardize formats
3. **Resolve** — Create views that join to reference tables for foreign keys
4. **Validate** — Check match rates, investigate unresolved records
5. **Rebuild** — Drop and recreate clean tables from views

### File Structure

```text
maint_db/
├── data/
│   └── factory_training.db
├── sql/
│   ├── 01_staging_views.sql      # Normalization views
│   ├── 02_resolution_views.sql   # FK resolution views  
│   └── 03_clean_tables.sql       # Final materialized tables
├── pipeline/
│   ├── normalize.py              # Python normalization functions
│   ├── run_pipeline.py           # Main orchestration script
│   └── validate.py               # Match rate checks
└── tests/
    └── test_normalization.py     # Unit tests for normalize functions
```

### Next Steps (Beyond This Workshop)

- **dbt** for production pipelines with testing and documentation
- **Great Expectations** or **Soda** for advanced data quality checks
- **Dagster** or **Prefect** for scheduled orchestration
- **OpenSearch/Elasticsearch** for full-text search layer (Part 2 of this workshop)
