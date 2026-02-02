# Scenario 6: Normalization Catch-Up

## Goal

Complete the normalization coverage for `incidents_clean` by adding functions for the three remaining raw fields:

1. `zone_ref_raw` → `zone_code`
2. `severity_raw` → `severity`
3. `reported_time_raw` → `reported_time`

This prepares our data for the searchable layer (OpenSearch) where we want only clean, normalized data—no raw fields propagated.

---

## Background

The current `incidents_clean` table normalizes 5 fields:

| Raw Field | Normalized Field | Function |
|-----------|------------------|----------|
| `machine_ref_raw` | `machine_code` | `normalize_machine_ref()` |
| `shift_code_ref_raw` | `shift_code` | `normalize_shift_code()` |
| `employee_ref_raw` | `badge_id` | `normalize_employee_ref()` |
| `incident_type_raw` | `incident_type` | `normalize_incident_type()` |
| `incident_time_raw` | `incident_time` | `parse_incident_time()` |

But three raw fields are still **not normalized**:

| Raw Field | Target | Status |
|-----------|--------|--------|
| `zone_ref_raw` | `zone_code` | ❌ Missing |
| `severity_raw` | `severity` | ❌ Missing |
| `reported_time_raw` | `reported_time` | ❌ Missing |

---

## Step 1: Explore the Data

### 1.1 Zone References

```sql
-- What do zone_ref_raw values look like?
SELECT zone_ref_raw, COUNT(*) as cnt
FROM incident_reports_raw
GROUP BY zone_ref_raw
ORDER BY cnt DESC
LIMIT 20;

-- What are the canonical zone codes?
SELECT zone_code, zone_name FROM zones ORDER BY zone_code;
```

**Variations found:**

| Variant | Example | Count |
|---------|---------|-------|
| Lowercase | `z-03` | 58 |
| Verbose prefix | `Zone Z-03` | 53 |
| No hyphen | `Z03` | 52 |
| Extra spaces | ` Z-03 ` | 49 |
| Canonical | `Z-03` | 47 |
| Empty | `` | 9 |
| Placeholder | `ZONE-UNKNOWN` | 8 |
| Invalid number | `Z-99` | 6 |

### 1.2 Severity Values

```sql
-- What do severity_raw values look like?
SELECT severity_raw, COUNT(*) as cnt
FROM incident_reports_raw
GROUP BY severity_raw
ORDER BY cnt DESC;
```

**Variations found:**

| Canonical | Raw Variants |
|-----------|--------------|
| `low` | `LOW`, `low`, `L`, `sev1`, `1`, `minor` |
| `medium` | `MED`, `medium`, `M`, `sev2`, `2`, `moderate`, `mdeium` (typo) |
| `high` | `HIGH`, `high`, `H`, `sev3`, `3`, `major` |
| `critical` | `sev4` |

### 1.3 Reported Time

```sql
-- What do reported_time_raw values look like?
SELECT reported_time_raw, COUNT(*) as cnt
FROM incident_reports_raw
GROUP BY reported_time_raw
ORDER BY cnt DESC
LIMIT 20;
```

**Formats found:**

| Format | Example |
|--------|---------|
| ISO date only | `2024-04-18` |
| MM/DD/YYYY | `12/10/2024` |
| DD-Mon-YYYY with full time | `31-May-2025 02:20:12` |
| DD-Mon-YYYY with HH:MM | `29-Oct-2025 21:02` |
| DD-Mon-YYYY with hour only | `29-Oct-2024 00` |
| DD-Mon-YYYY no time | `30-Jan-2024` |

This is similar to `incident_time_raw` but may have additional patterns.

---

## Step 2: Write the Normalization Functions

Add these functions to `pipeline/normalize.py`:

### 2.1 `normalize_zone_ref()`

```python
def normalize_zone_ref(raw: str | None) -> str | None:
    """
    Normalize a raw zone reference to canonical format (Z-XX).

    Args:
        raw: The raw zone_ref_raw string from incident_reports_raw

    Returns:
        Canonical zone code (e.g., 'Z-03') or None if unmatchable

    Examples:
        >>> normalize_zone_ref('Z-03')
        'Z-03'
        >>> normalize_zone_ref('z-03')
        'Z-03'
        >>> normalize_zone_ref('Z03')
        'Z-03'
        >>> normalize_zone_ref('Zone Z-03')
        'Z-03'
        >>> normalize_zone_ref(' Z-03 ')
        'Z-03'
        >>> normalize_zone_ref('Z-99')  # Invalid zone
        >>> normalize_zone_ref('ZONE-UNKNOWN')
        >>> normalize_zone_ref('')
        >>> normalize_zone_ref(None)
    """
    pass  # TODO: Implement
```

**Requirements:**

- Valid zones are Z-01 through Z-06 only
- Handle case insensitivity
- Handle "Zone" prefix
- Handle missing hyphen
- Handle extra whitespace
- Return `None` for invalid zone numbers (Z-99) or placeholders

### 2.2 `normalize_severity()`

```python
def normalize_severity(raw: str | None) -> str | None:
    """
    Normalize a raw severity value to canonical format.

    Canonical values: 'low', 'medium', 'high', 'critical'

    Args:
        raw: The raw severity_raw string from incident_reports_raw

    Returns:
        Canonical severity or None if unmatchable

    Examples:
        >>> normalize_severity('LOW')
        'low'
        >>> normalize_severity('sev1')
        'low'
        >>> normalize_severity('1')
        'low'
        >>> normalize_severity('minor')
        'low'
        >>> normalize_severity('MED')
        'medium'
        >>> normalize_severity('moderate')
        'medium'
        >>> normalize_severity('mdeium')  # typo
        'medium'
        >>> normalize_severity('HIGH')
        'high'
        >>> normalize_severity('major')
        'high'
        >>> normalize_severity('sev4')
        'critical'
        >>> normalize_severity('')
        >>> normalize_severity(None)
    """
    pass  # TODO: Implement
```

**Requirements:**

- Map numeric values: 1→low, 2→medium, 3→high, 4+→critical
- Map sev1/sev2/sev3/sev4 patterns
- Map word variants (minor, moderate, major)
- Handle common typos (`mdeium`)
- Case insensitive

### 2.3 `parse_reported_time()`

```python
def parse_reported_time(raw: str | None) -> str | None:
    """
    Parse a raw reported time string to ISO format (YYYY-MM-DD HH:MM:SS).

    This function handles the same formats as parse_incident_time().
    Consider whether to reuse that function or handle additional patterns.

    Args:
        raw: The raw reported_time_raw string

    Returns:
        ISO formatted datetime (YYYY-MM-DD HH:MM:SS) or None if unparseable

    Examples:
        >>> parse_reported_time('2024-04-18')
        '2024-04-18 00:00:00'
        >>> parse_reported_time('31-May-2025 02:20:12')
        '2025-05-31 02:20:12'
        >>> parse_reported_time('12/10/2024')
        '2024-12-10 00:00:00'
    """
    pass  # TODO: Implement
```

**Design Decision:**

The `parse_incident_time()` function already handles these formats. Options:

1. **Reuse directly**: Just alias `parse_reported_time = parse_incident_time`
2. **Wrapper function**: Call `parse_incident_time()` internally but with a different name for clarity
3. **Separate implementation**: If `reported_time_raw` has unique patterns not in `incident_time_raw`

Recommend option 2—a thin wrapper that calls the existing function.

---

## Step 3: Write Tests

Add tests to `tests/test_normalize.py`:

```python
# tests/test_normalize.py

class TestNormalizeZoneRef:
    """Tests for normalize_zone_ref()"""

    def test_canonical_format(self):
        assert normalize_zone_ref("Z-03") == "Z-03"

    def test_lowercase(self):
        assert normalize_zone_ref("z-03") == "Z-03"

    def test_no_hyphen(self):
        assert normalize_zone_ref("Z03") == "Z-03"

    def test_verbose_prefix(self):
        assert normalize_zone_ref("Zone Z-03") == "Z-03"

    def test_extra_whitespace(self):
        assert normalize_zone_ref(" Z-03 ") == "Z-03"

    def test_all_valid_zones(self):
        for i in range(1, 7):
            assert normalize_zone_ref(f"Z-0{i}") == f"Z-0{i}"

    def test_invalid_zone_number(self):
        assert normalize_zone_ref("Z-99") is None
        assert normalize_zone_ref("Z-00") is None
        assert normalize_zone_ref("Z-07") is None

    def test_placeholder_values(self):
        assert normalize_zone_ref("ZONE-UNKNOWN") is None
        assert normalize_zone_ref("n/a") is None

    def test_empty_and_none(self):
        assert normalize_zone_ref("") is None
        assert normalize_zone_ref(None) is None


class TestNormalizeSeverity:
    """Tests for normalize_severity()"""

    def test_canonical_values(self):
        assert normalize_severity("low") == "low"
        assert normalize_severity("medium") == "medium"
        assert normalize_severity("high") == "high"
        assert normalize_severity("critical") == "critical"

    def test_uppercase(self):
        assert normalize_severity("LOW") == "low"
        assert normalize_severity("MED") == "medium"
        assert normalize_severity("HIGH") == "high"

    def test_numeric_values(self):
        assert normalize_severity("1") == "low"
        assert normalize_severity("2") == "medium"
        assert normalize_severity("3") == "high"
        assert normalize_severity("4") == "critical"

    def test_sev_pattern(self):
        assert normalize_severity("sev1") == "low"
        assert normalize_severity("sev2") == "medium"
        assert normalize_severity("sev3") == "high"
        assert normalize_severity("sev4") == "critical"

    def test_word_variants(self):
        assert normalize_severity("minor") == "low"
        assert normalize_severity("moderate") == "medium"
        assert normalize_severity("major") == "high"

    def test_single_letter(self):
        assert normalize_severity("L") == "low"
        assert normalize_severity("M") == "medium"
        assert normalize_severity("H") == "high"

    def test_typos(self):
        assert normalize_severity("mdeium") == "medium"

    def test_empty_and_none(self):
        assert normalize_severity("") is None
        assert normalize_severity(None) is None


class TestParseReportedTime:
    """Tests for parse_reported_time()"""

    def test_iso_date(self):
        assert parse_reported_time("2024-04-18") == "2024-04-18 00:00:00"

    def test_dmy_full_time(self):
        assert parse_reported_time("31-May-2025 02:20:12") == "2025-05-31 02:20:12"

    def test_dmy_partial_time(self):
        assert parse_reported_time("29-Oct-2025 21:02") == "2025-10-29 21:02:00"

    def test_dmy_hour_only(self):
        assert parse_reported_time("29-Oct-2024 00") == "2024-10-29 00:00:00"

    def test_dmy_no_time(self):
        assert parse_reported_time("30-Jan-2024") == "2024-01-30 00:00:00"

    def test_mdy_format(self):
        assert parse_reported_time("12/10/2024") == "2024-12-10 00:00:00"

    def test_empty_and_none(self):
        assert parse_reported_time("") is None
        assert parse_reported_time(None) is None
```

Run tests:

```bash
uv run pytest tests/test_normalize.py -v -k "zone or severity or reported"
```

---

## Step 4: Update the Pipeline

### 4.1 Update `build_incidents_clean.py`

Add the new imports:

```python
from pipeline.normalize import (
    normalize_machine_ref,
    normalize_shift_code,
    normalize_incident_type,
    create_employee_normalizer,
    parse_incident_time,
    normalize_zone_ref,      # NEW
    normalize_severity,       # NEW
    parse_reported_time,      # NEW
)
```

Register the new UDFs:

```python
def register_udfs(conn: sqlite3.Connection, employees: list) -> None:
    """Register all normalization functions as SQLite UDFs."""

    conn.create_function("normalize_machine_ref", 1, normalize_machine_ref)
    conn.create_function("normalize_shift_code", 1, normalize_shift_code)
    conn.create_function("normalize_incident_type", 1, normalize_incident_type)
    conn.create_function("parse_incident_time", 1, parse_incident_time)
    conn.create_function("normalize_zone_ref", 1, normalize_zone_ref)        # NEW
    conn.create_function("normalize_severity", 1, normalize_severity)         # NEW
    conn.create_function("parse_reported_time", 1, parse_reported_time)       # NEW

    # Employee normalizer needs lookup data baked in
    normalize_employee_ref = create_employee_normalizer(employees)
    conn.create_function("normalize_employee_ref", 1, normalize_employee_ref)

    print("✓ Registered 8 normalization UDFs")  # Updated count
```

Update the view to include normalized columns:

```python
def create_view(conn: sqlite3.Connection) -> None:
    """Create the comprehensive incidents view with all normalizations."""

    conn.execute("DROP VIEW IF EXISTS v_incidents_clean")
    conn.execute(
        """
        CREATE VIEW v_incidents_clean AS
        SELECT 
            incident_id,
            
            -- Raw columns preserved for debugging
            incident_time_raw,
            reported_time_raw,
            shift_code_ref_raw,
            employee_ref_raw,
            machine_ref_raw,
            zone_ref_raw,
            incident_type_raw,
            severity_raw,
            description,
            created_at_iso,
            
            -- Normalized columns
            normalize_machine_ref(machine_ref_raw) as machine_code,
            normalize_shift_code(shift_code_ref_raw) as shift_code,
            normalize_employee_ref(employee_ref_raw) as badge_id,
            normalize_incident_type(incident_type_raw) as incident_type,
            parse_incident_time(incident_time_raw) as incident_time,
            normalize_zone_ref(zone_ref_raw) as zone_code,           -- NEW
            normalize_severity(severity_raw) as severity,             -- NEW
            parse_reported_time(reported_time_raw) as reported_time   -- NEW
            
        FROM incident_reports_raw
    """
    )

    print("✓ Created view: v_incidents_clean")
```

Update the stats reporting:

```python
def materialize_table(conn: sqlite3.Connection) -> None:
    """Materialize the view to a table for querying."""

    conn.execute("DROP TABLE IF EXISTS incidents_clean")
    conn.execute("CREATE TABLE incidents_clean AS SELECT * FROM v_incidents_clean")
    conn.commit()

    cursor = conn.execute("SELECT COUNT(*) FROM incidents_clean")
    total = cursor.fetchone()[0]

    cursor = conn.execute(
        """
        SELECT 
            SUM(CASE WHEN machine_code IS NOT NULL THEN 1 ELSE 0 END) as machines,
            SUM(CASE WHEN shift_code IS NOT NULL THEN 1 ELSE 0 END) as shifts,
            SUM(CASE WHEN badge_id IS NOT NULL THEN 1 ELSE 0 END) as employees,
            SUM(CASE WHEN incident_type IS NOT NULL THEN 1 ELSE 0 END) as types,
            SUM(CASE WHEN incident_time IS NOT NULL THEN 1 ELSE 0 END) as times,
            SUM(CASE WHEN zone_code IS NOT NULL THEN 1 ELSE 0 END) as zones,
            SUM(CASE WHEN severity IS NOT NULL THEN 1 ELSE 0 END) as severities,
            SUM(CASE WHEN reported_time IS NOT NULL THEN 1 ELSE 0 END) as reported
        FROM incidents_clean
    """
    )
    machines, shifts, employees, types, times, zones, severities, reported = cursor.fetchone()

    print(f"✓ Materialized table: incidents_clean ({total} rows)")
    print(
        f"  Match rates: machine={100*machines/total:.1f}%, shift={100*shifts/total:.1f}%, "
        f"employee={100*employees/total:.1f}%, type={100*types/total:.1f}%, time={100*times/total:.1f}%"
    )
    print(
        f"               zone={100*zones/total:.1f}%, severity={100*severities/total:.1f}%, "
        f"reported={100*reported/total:.1f}%"
    )
```

---

## Step 5: Run and Validate

### 5.1 Run Tests

```bash
uv run pytest tests/test_normalize.py -v
```

### 5.2 Run the Pipeline

```bash
uv run python pipeline/build_incidents_clean.py
```

**Expected output:**

```
Running consolidated data cleaning pipeline...

✓ Loaded 60 employees for lookup
✓ Registered 8 normalization UDFs
✓ Created view: v_incidents_clean
✓ Materialized table: incidents_clean (456 rows)
  Match rates: machine=96.5%, shift=98.2%, employee=97.8%, type=99.1%, time=98.5%
               zone=94.3%, severity=99.6%, reported=97.4%

✓ Pipeline complete. Query from: incidents_clean
```

### 5.3 Validate New Columns

```sql
-- Check zone normalization
SELECT zone_code, COUNT(*) as cnt
FROM incidents_clean
WHERE zone_code IS NOT NULL
GROUP BY zone_code
ORDER BY zone_code;

-- Check severity normalization
SELECT severity, COUNT(*) as cnt
FROM incidents_clean
WHERE severity IS NOT NULL
GROUP BY severity
ORDER BY severity;

-- Check reported_time parsing
SELECT 
    reported_time_raw,
    reported_time
FROM incidents_clean
WHERE reported_time IS NOT NULL
LIMIT 10;

-- What couldn't be normalized?
SELECT zone_ref_raw, COUNT(*) as cnt
FROM incidents_clean
WHERE zone_code IS NULL
GROUP BY zone_ref_raw;
```

---

## Success Criteria

- [ ] All three normalization functions implemented in `pipeline/normalize.py`
- [ ] All tests pass: `uv run pytest tests/test_normalize.py -v`
- [ ] Pipeline runs successfully with 8 UDFs registered
- [ ] Match rates for new fields:
  - `zone_code`: ≥94%
  - `severity`: ≥99%
  - `reported_time`: ≥97%
- [ ] `incidents_clean` table now has all 8 normalized columns

---

## Next Steps

With all fields normalized, we're ready for **Phase 2A: Searchable Database with OpenSearch**.

The OpenSearch index will contain only the clean, normalized fields—no `*_raw` columns will be indexed, keeping the search layer clean and consistent.
