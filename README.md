# Factory Maintenance Database — Training Exercise

A hands-on data cleaning and analysis workshop. Work with messy, inconsistent factory operations data and build tools to clean, query, and search it.

📖 **Start here:** [PROBLEM.md](PROBLEM.md) — Full problem statement and challenges

## Workshop Overview

| Part  | Focus                         | Format                          |
| ----- | ----------------------------- | ------------------------------- |
| **1** | SQL Analysis & Data Cleaning  | 3 together + 2 independent      |
| **2** | Search & Transformation Layer | 1 together, 1-2 independent     |
| **3** | Agentic Interface             | Discussion + optional extension |

### Part 1 Scenarios

| #   | Question                                     | Format      | Key Challenge                          |
| --- | -------------------------------------------- | ----------- | -------------------------------------- |
| 1   | Which 3 machines have the most incidents?    | Together    | `machine_ref_raw` normalization        |
| 2   | Is the night shift more dangerous?           | Together    | Rate calculation + joins               |
| 3   | Which 5 employees appear in most incidents?  | Independent | `employee_ref_raw` normalization       |
| 4   | Which machine type has highest failure rate? | Independent | Compound cleaning + joins              |
| 5   | When do problems cluster?                    | Together    | Time-based patterns → motivates Part 2 |

There's also a scenario 6 that cleans up the rest of the dirty references in `incident_reports_raw`, but that's 
more of a catch-up exercise.

### Part 2

This is started in another branch - feature/opensearch-indexer.
There's just enough there to index incidents_clean and set up OpenSearch running in docker ready to answer questions.


## Quick Start (to refine later)

```bash
# View the database
sqlite3 data/factory_training.db ".tables"
sqlite3 data/factory_training.db "SELECT COUNT(*) FROM incident_reports_raw;"

# Or use a GUI like SQLite3 Editor (VS Code) or DBeaver
```

## Project Structure

```sh
maint_db/
├── PROBLEM.md               # 📖 Workshop instructions and challenges
├── MAINT_DATA.md            # 📋 Data specification (instructor reference)
├── DATA_CLEANING_APPROACH.md # 🔧 Pipeline patterns and best practices
├── data/
│   └── factory_training.db  # The messy database to analyze
├── schema/
│   └── schema.sql           # Database schema
├── scripts/                 # Data generation (instructor use)
│   ├── create_factory_db.py
│   ├── append_factory_data.py
│   └── validate_data.py
└── util/                    # Shared helpers
    └── data_helpers.py
```

## The Data

| Clean Tables     | Messy Tables            |
| ---------------- | ----------------------- |
| `employees`      | `shifts_raw`            |
| `machines`       | `shift_assignments_raw` |
| `machine_types`  | `incident_reports_raw`  |
| `zones`          | `maintenance_logs_raw`  |
| `incident_types` | `layout_raw`            |

**What's Messy:**

- 9+ date/time formats
- Inconsistent employee refs (badge IDs, names, employee IDs)
- Inconsistent machine codes (M-017, m017, Machine 17)
- Incident type synonyms and typos
- Missing and bogus references

**Discoverable Outliers:**

- Specific machines (M-003, M-017, M-024) with high failure rates
- Night shift with ~1.4x incident rate vs day shift
- 4-5 employees overrepresented in incidents

---

## For Instructors

### Regenerating the Database

```bash
python scripts/create_factory_db.py data/factory_training.db --seed 42 --overwrite
```

### Adding More Data (Testing Incremental Pipelines)

```bash
python scripts/append_factory_data.py data/factory_training.db --days 30 --seed 100
```

### Validating Data Characteristics

```bash
python scripts/validate_data.py data/factory_training.db
```
