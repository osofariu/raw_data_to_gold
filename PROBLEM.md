# Factory Incident Analysis — Training Exercise

## The Story

You've just joined the data team at **Precision Manufacturing Co.**, a mid-sized factory that produces industrial components. The factory runs 24/7 with three shifts (Day, Swing, Night) and has about 40 machines across 6 zones.

Management is concerned about **incident rates** — machine failures, safety violations, quality defects, and the occasional injury. They've been collecting data for two years, but it's a mess:

- Different systems log timestamps in different formats
- Employees are identified sometimes by badge number, sometimes by name, sometimes by employee ID
- Machine references are inconsistent ("M-017", "m017", "Machine 17", etc.)
- Incident types have synonyms and typos ("Machine Failure", "MECH_FAIL", "machine_fail")

Your job is to **make sense of this data** so the company can answer questions like:

- Which machines break down the most?
- Are certain employees involved in more incidents?
- Is the night shift really more dangerous?
- Where in the factory do most incidents happen?

---

## Workshop Structure

This workshop has three parts, each following a **"together, then independent"** pattern:

| Part  | Focus                         | Together          | Independent        |
| ----- | ----------------------------- | ----------------- | ------------------ |
| **1** | SQL Analysis & Data Cleaning  | 3 scenarios       | 2 scenarios        |
| **2** | Search & Transformation Layer | 1 scenario        | 1-2 scenarios      |
| **3** | Agentic Interface (Advanced)  | Discussion + demo | Optional extension |

---

## Setup

### Prerequisites

- Python 3.10+
- SQLite3 (usually pre-installed on macOS/Linux)

### Recommended Tools

| Tool                                     | Purpose                                |
| ---------------------------------------- | -------------------------------------- |
| **SQLite3 Editor** (VS Code extension)   | Browse and query the database visually |
| **DBeaver** or **DB Browser for SQLite** | Alternative database GUI               |
| **uv** or **pip**                        | Python package management              |

### Getting Started

1. Clone this repository
2. The database is at `data/factory_training.db`
3. Open the database in your SQLite tool of choice
4. Review the schema in `schema/schema.sql`

```bash
# Quick peek at the data
sqlite3 data/factory_training.db ".tables"
sqlite3 data/factory_training.db "SELECT COUNT(*) FROM incident_reports_raw;"
```

---

## The Data

The database contains ~10 tables:

| Table                   | Description            | Data Quality          |
| ----------------------- | ---------------------- | --------------------- |
| `employees`             | Staff records          | ✅ Clean               |
| `machines`              | Equipment inventory    | ✅ Clean               |
| `machine_types`         | Equipment categories   | ✅ Clean               |
| `zones`                 | Factory areas          | ✅ Clean               |
| `incident_types`        | Incident categories    | ✅ Clean               |
| `shifts_raw`            | Shift schedules        | ⚠️ Messy timestamps    |
| `shift_assignments_raw` | Who worked which shift | ⚠️ Messy employee refs |
| `incident_reports_raw`  | Incident records       | ⚠️ Very messy          |
| `maintenance_logs_raw`  | Repair records         | ⚠️ Messy               |
| `layout_raw`            | Machine locations      | ⚠️ Some bad refs       |

**Clean tables** have proper foreign keys and consistent formatting.  
**Raw tables** have string-based references that don't always match.

---

# Part 1: SQL Analysis & Data Cleaning

## 1A: Together (Instructor-Led)

We'll work through these two scenarios as a group, demonstrating the full workflow:

1. Examine the schema and identify what we need
2. Explore the messy fields
3. Discuss cleaning strategies (views, tables, migration)
4. Implement the solution
5. Answer the question and visualize the result

---

### Scenario 1: Which 3 machines have the most incidents?

**The Mess:** `machine_ref_raw` in `incident_reports_raw`

A single machine (e.g., M-017) appears in the data as:

- `M-017`, `m-017`, `M017`, `m017`
- `Machine 17`, `Machine 017`
- `017`, `17`
- `MX-017` (typos)
- Leading/trailing whitespace

**Your Task:**

1. Explore the distinct values in `machine_ref_raw`
2. Create a cleaning strategy (view or table) that maps raw values → canonical `machine_code`
3. Build a query that counts incidents per machine
4. Identify the top 3 problem machines

**Skills Practiced:**

- Pattern matching with `LIKE`, `GLOB`, or `CASE`
- String functions: `TRIM()`, `UPPER()`, `REPLACE()`
- Creating views for a clean query layer
- Basic aggregation with `GROUP BY` and `ORDER BY`

**Expected Insight:** You should find that M-003, M-017, and M-024 have significantly more incidents than average (they're known problem machines).

---

### Scenario 2: Is the night shift really more dangerous?

**The Question:** What's the incident rate per shift type (Day/Swing/Night)?

**The Mess:** Connecting incidents to shifts

The good news: `shifts_raw.shift_name` is already clean (Day, Swing, Night).  
The challenge: You need to calculate a **rate** (incidents per shift), not just a count.

**Your Task:**

1. Count how many shifts of each type exist
2. Count how many incidents occurred during each shift type
3. Calculate the incident rate: `incidents / shift_count`
4. Visualize with a simple bar chart (optional, using matplotlib)

**Skills Practiced:**

- Joining `incident_reports_raw` → `shifts_raw` via `shift_code_ref_raw`
- Handling missing/bad shift references
- Rate calculations vs raw counts
- Basic data visualization

**Expected Insight:** Night shift should show a notably higher incident rate (~1.3-1.5x) compared to day shift.

---

## 1B: Independent Work

Now apply what you learned to these two scenarios. The cleaning challenges are **different** — you can't just copy-paste the previous solutions.

---

### Scenario 3: Which 5 employees appear in the most incidents?

**The Mess:** `employee_ref_raw` in `incident_reports_raw`

Employee references are even messier than machines. The same person appears as:

- Badge ID: `B0042`, `b0042`, `B 0042`
- Employee ID format: `EMP-42`, `EMP42`
- Full name: `Casey Patel`, `CASEY PATEL`, `casey patel`
- Just the number: `42`
- Placeholder values: `UNKNOWN`, `n/a`, empty string

**Your Task:**

1. Explore the distinct patterns in `employee_ref_raw`
2. Create a cleaning strategy that maps raw values → `employee_id` or `badge_id`
3. Handle unmatchable references gracefully (count them separately)
4. Identify the top 5 employees by incident involvement

**Hints:**

- The `employees` table has `badge_id`, `first_name`, `last_name`, and `employee_id`
- You may need multiple matching strategies (badge pattern, name lookup, ID extraction)
- Some references are genuinely unmatchable — that's okay, just track how many

**Expected Insight:** A small number of employees (4-5) appear in a disproportionate share of incidents.

---

### Scenario 4: Which machine type has the highest failure rate?

**The Mess:** Multiple fields need cleaning

This scenario chains together multiple cleaning steps:

1. Clean `incident_type_raw` to identify machine failures
2. Clean `machine_ref_raw` to match to actual machines
3. Join through `machines` → `machine_types`
4. Calculate failure rate per machine type

**Incident Type Variants:**

- `machine_failure`, `Machine Failure`, `MECH_FAIL`
- `machine_fail`, `Mach failure`, `machine failure` (trailing space)
- Typos: `Mahcine Failure`, `machin_failure`

**Your Task:**

1. Create a view/logic to normalize `incident_type_raw` → canonical type
2. Filter to only machine failure incidents
3. Join to get machine type for each incident
4. Calculate: failures per machine type (or per machine of that type)

**Hints:**

- Use `incident_types` table for canonical names
- Consider: is "failure rate" = total failures, or failures per machine of that type?
- The `machines` table links `machine_code` → `machine_type_id`

**Expected Insight:** Press and Conveyor types should show higher failure rates than RobotArm or Mixer.

---

## Part 1 Success Criteria

When you've completed Part 1, you should be able to:

- [ ] Parse and normalize machine references → match 95%+ of incidents to valid machines
- [ ] Parse and normalize employee references → match 90%+ of incidents to valid employees  
- [ ] Normalize incident types → map all variants to canonical types
- [ ] Answer all four scenario questions with clean, readable queries
- [ ] Your answers reveal the expected outlier patterns

---

## 1C: Together — Bridge to Part 2

This final instructor-led scenario demonstrates where SQL starts to struggle — and motivates the tools we'll explore in Part 2.

---

### Scenario 5: When Do Problems Cluster?

**The Business Question:**

Management has noticed that incidents rarely happen in isolation. When one thing goes wrong, other problems often follow within a few hours. They want to understand:

1. How often do we see **"incident clusters"** (3+ incidents within a 4-hour window)?
2. What **times of day** are clusters most common?
3. Are clusters associated with specific **shifts, zones, or machine types**?

**The Mess:** Time-based pattern detection in SQL

This requires your cleaned data from Scenarios 1-4, plus some awkward SQL:

| Task                                             | SQL Approach              | Difficulty |
| ------------------------------------------------ | ------------------------- | ---------- |
| Find incidents with 2+ others within ±2 hours    | Self-join with time range | Moderate   |
| Group overlapping windows into distinct clusters | Gap-and-island problem    | Hard       |
| Bucket by hour-of-day and aggregate              | `strftime` + GROUP BY     | Moderate   |
| Break down by shift × zone × machine type        | Multiple nested GROUP BYs | Hard       |
| Visualize the distribution                       | Export to Python          | Extra step |

**Your Task:**

1. Using your `incidents_clean` view/table, find incidents that have at least 2 other incidents within a 4-hour window (±2 hours)
2. Try to identify distinct "cluster events" (groups of overlapping incidents)
3. Analyze: what time of day do clusters happen? Which shifts? Which zones?

**Sample SQL (just step 1):**

```sql
-- Find incidents that have 2+ other incidents within ±2 hours
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
  GROUP BY a.incident_id
)
SELECT * FROM incident_with_neighbors WHERE nearby_count >= 2;
```

**Skills Practiced:**

- Self-joins with time-based conditions
- Window functions and CTEs
- The pain of time-series analysis in SQL

**The Point:**

This query works, but extending it to:

- Group overlapping windows into single cluster events
- Aggregate by multiple dimensions (hour × shift × zone)
- Visualize trends over time

...quickly becomes 50+ lines of complex SQL. This is exactly what search and analytics tools are designed for.

**Expected Insight:** You should find that clusters are more common during shift transitions and on night shifts. But getting there in SQL is painful — which is why we're moving to Part 2.

---

# Part 2: Search & Transformation Layer

## The Problem with SQL

As Scenario 5 demonstrated, SQL struggles with:

- Time-series pattern detection and windowing
- Multi-dimensional aggregations
- Full-text search on descriptions
- Interactive exploration and visualization

## 2A: Together (Instructor-Led)

We'll discuss and implement:

1. Why you might want a searchable layer on top of your cleaned data
2. Options: OpenSearch/Elasticsearch, ClickHouse, DuckDB, Postgres with indexing
3. Designing a search-friendly document model
4. Building a simple ETL pipeline

### Demo Scenario: Searchable Incident Index

Transform your cleaned incident data into a searchable format with:

- Full-text search on descriptions
- Faceted filtering by machine, employee, zone, severity
- Date range queries
- Pre-computed aggregations

## 2B: Independent Work

### Scenario 6: Build Your Own Search Layer

Using the approach demonstrated, build a searchable layer that:

1. Indexes all cleaned incidents
2. Supports at least 3 filter dimensions
3. Handles incremental updates (test with `scripts/append_factory_data.py`)
4. **Bonus:** Solve the clustering problem from Scenario 5 using your search layer

---

# Part 3: Agentic Interface (Advanced)

## Discussion: Why Add an AI Layer?

Once you have clean, searchable data, an AI agent can:

- Answer natural language questions
- Combine multiple queries to answer complex questions
- Explain its reasoning and cite sources
- Handle ambiguity gracefully

## Key Considerations

- What tools/functions does the agent need access to?
- How do you prevent hallucination with grounded data?
- When should the agent query vs. when should it use cached aggregations?
- How do you handle questions the data can't answer?

## Optional Extension

Build a simple agent that can answer questions like:

- "What happened with machine M-017 last month?"
- "Show me all safety incidents on night shift"
- "Which zone should we prioritize for safety improvements?"

---

# Staying Current

The factory keeps operating! New shifts, incidents, and maintenance logs are added regularly.

Your pipeline should handle incremental updates:

- New data arrives (we'll add it to the database)
- Your clean layer updates automatically (or with a simple command)
- Your search layer stays in sync

Test this by running:

```bash
python scripts/append_factory_data.py --days 7
```

---

# Tips

1. **Start with exploration** — Spend time understanding the data before trying to clean it
2. **Document your assumptions** — What do you do with records you can't match?
3. **Test incrementally** — Verify each cleaning step before moving on
4. **Think about edge cases** — What if a machine was retired? What if an employee was terminated?
5. **Good enough is good enough** — 95% match rate is often fine; chasing 100% has diminishing returns

---

# Quick Reference: What's Messy Where

| Field               | Table                          | Variants                                    |
| ------------------- | ------------------------------ | ------------------------------------------- |
| `machine_ref_raw`   | incidents, maintenance, layout | M-017, m017, Machine 17, 017                |
| `employee_ref_raw`  | incidents, assignments         | B0042, EMP-42, Casey Patel, 42              |
| `zone_ref_raw`      | incidents, layout              | Z-02, z02, Zone Z-02                        |
| `incident_type_raw` | incidents                      | machine_failure, MECH_FAIL, Machine Failure |
| `severity_raw`      | incidents                      | low, LOW, 1, minor, L                       |
| `*_time_raw`        | all raw tables                 | 9 different date formats                    |

Good luck!
