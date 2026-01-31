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

## The Exercise

This exercise has two main parts:

### Part 1: SQL Analysis

Using only SQL, clean and analyze the data to answer questions about incidents, machines, employees, and shifts.

**What you'll learn:**
- Parsing inconsistent date/time formats
- Entity resolution (matching messy references to canonical records)
- Creating views to build a clean query layer
- Writing analytical queries with joins, aggregations, and window functions

### Part 2: Search & Transformation Layer

Build a searchable layer on top of the cleaned data. This could be:
- **OpenSearch/Elasticsearch** for full-text search and faceted filtering
- **A data warehouse** with pre-computed aggregations
- **Another approach** of your choosing

**What you'll learn:**
- Designing search-friendly data models
- Building ETL/transformation pipelines
- Handling incremental updates (the factory keeps generating new data!)

### Part 3 (Advanced): Agentic Interface

Build an AI-powered interface that can answer natural language questions about the data.

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

## Part 1 Challenges

### Level 1: Understand the Mess

Before cleaning, understand what you're dealing with:

1. How many distinct date formats appear in `incident_time_raw`?
2. What are all the ways employees are referenced in `incident_reports_raw`?
3. How many incident records can't be matched to a valid employee?

### Level 2: Build a Clean Layer

Create views or tables that normalize the raw data:

1. **`incidents_clean`** — Incidents with parsed timestamps and resolved foreign keys
2. **`shifts_clean`** — Shifts with proper start/end timestamps
3. **`assignments_clean`** — Shift assignments with resolved employee IDs

### Level 3: Answer Business Questions

Using your clean layer, write queries to answer:

1. Which 3 machines have the most incidents?
2. What's the incident rate per shift type (Day/Swing/Night)?
3. Which 5 employees appear in the most incidents?
4. Which machine type has the highest failure rate?
5. Which zone has the most incidents per machine?
6. Is there a correlation between time of day and incident severity?

### Level 4: Validate Your Work

Your analysis should reveal these patterns (if it doesn't, your cleaning may have issues):

- Some specific machines have **2-3x** the average incident rate
- Night shift has a notably higher incident rate than day shift
- A small number of employees appear in a disproportionate share of incidents

---

## Part 2 Challenges

### The Problem with SQL

SQL is great for answering specific questions, but:
- Complex queries are slow to write and run
- Full-text search on descriptions is limited
- Aggregations must be recomputed each time
- It's hard to explore the data interactively

### Your Task

Build a layer that makes the data easier to explore:

1. **Full-text search** — Find incidents by description keywords
2. **Faceted filtering** — Filter by machine, employee, zone, severity, date range
3. **Pre-computed aggregations** — Incident counts, trends, rankings
4. **Incremental updates** — Handle new data without full rebuild

### Suggested Approach: OpenSearch

OpenSearch (or Elasticsearch) is well-suited for this:
- Built-in full-text search
- Faceted aggregations
- Date histograms for trends
- Good query performance

But you're welcome to use other tools: ClickHouse, DuckDB, Postgres with proper indexing, etc.

---

## Staying Current

The factory keeps operating! New shifts, incidents, and maintenance logs are added regularly.

Your pipeline should handle incremental updates:
- New data arrives (we'll add it to the database)
- Your clean layer updates automatically (or with a simple command)
- Your search layer stays in sync

We'll test this by running `scripts/append_factory_data.py` to add more data.

---

## Success Criteria

### Part 1 Complete When:
- [ ] You can parse all date formats in the raw tables
- [ ] You can resolve 90%+ of employee/machine references
- [ ] You can answer the Level 3 questions with SQL
- [ ] Your answers reveal the expected outlier patterns

### Part 2 Complete When:
- [ ] You have a searchable interface for the data
- [ ] You can filter and search across multiple dimensions
- [ ] Your layer handles incremental updates

---

## Tips

1. **Start with exploration** — Spend time understanding the data before trying to clean it
2. **Document your assumptions** — What do you do with records you can't match?
3. **Test incrementally** — Verify each cleaning step before moving on
4. **Think about edge cases** — What if a machine was retired? What if an employee was terminated?

Good luck!
