# Factory Maintenance Database — Training Exercise

A data cleaning and analysis exercise for developers. Work with messy, inconsistent factory operations data and build tools to clean, query, and search it.

📖 **Start here:** [PROBLEM.md](PROBLEM.md) — Full problem statement and challenges

## Quick Start

```bash
# View the database
sqlite3 data/factory_training.db ".tables"
sqlite3 data/factory_training.db "SELECT COUNT(*) FROM incident_reports_raw;"

# Or use a GUI like SQLite3 Editor (VS Code) or DBeaver
```

## Project Structure

```
maint_db/
├── PROBLEM.md           # 📖 Student instructions and challenges
├── MAINT_DATA.md        # 📋 Data specification (internal reference)
├── data/
│   └── factory_training.db   # The messy database to analyze
├── schema/
│   └── schema.sql       # Database schema for reference
├── scripts/             # Data generation (internal)
│   ├── create_factory_db.py
│   ├── append_factory_data.py
│   └── validate_data.py
└── util/                # Shared helpers (internal)
    └── data_helpers.py
```

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

## The Data

| Clean Tables | Messy Tables |
|-------------|--------------|
| `employees` | `shifts_raw` |
| `machines` | `shift_assignments_raw` |
| `machine_types` | `incident_reports_raw` |
| `zones` | `maintenance_logs_raw` |
| `incident_types` | `layout_raw` |

**Data Quality Issues:**
- 9+ date/time formats
- Inconsistent employee references (badge IDs, names, employee IDs)
- Inconsistent machine codes
- Incident type synonyms and typos
- Missing and bogus references

**Discoverable Outliers:**
- Specific machines with high failure rates
- Night shift with elevated incident rate
- Employees overrepresented in incidents
