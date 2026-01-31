-- Factory Incident Database Schema
-- See MAINT_DATA.md for detailed specification

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

--------------------------------------------------------------------------------
-- REFERENCE TABLES (Clean)
-- These contain canonical lookup values with proper constraints.
--------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS machine_types (
  machine_type_id INTEGER PRIMARY KEY,
  type_name TEXT NOT NULL UNIQUE,
  category TEXT NOT NULL,
  typical_mtbf_hours INTEGER
);

CREATE TABLE IF NOT EXISTS incident_types (
  incident_type_id INTEGER PRIMARY KEY,
  incident_type TEXT NOT NULL UNIQUE,
  category TEXT NOT NULL,
  default_severity TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS zones (
  zone_id INTEGER PRIMARY KEY,
  zone_code TEXT NOT NULL UNIQUE,
  zone_name TEXT NOT NULL
);

--------------------------------------------------------------------------------
-- DIMENSION TABLES (Clean)
-- Core entities with consistent formatting and proper foreign keys.
--------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS employees (
  employee_id INTEGER PRIMARY KEY,
  badge_id TEXT NOT NULL UNIQUE,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  hire_date TEXT NOT NULL,     -- ISO yyyy-mm-dd
  role TEXT NOT NULL,
  status TEXT NOT NULL         -- active, leave, terminated
);

CREATE TABLE IF NOT EXISTS machines (
  machine_id INTEGER PRIMARY KEY,
  machine_code TEXT NOT NULL UNIQUE,  -- canonical code M-###
  machine_type_id INTEGER NOT NULL,
  vendor TEXT NOT NULL,
  install_date TEXT NOT NULL,         -- ISO yyyy-mm-dd
  status TEXT NOT NULL,               -- active, retired, maintenance
  FOREIGN KEY(machine_type_id) REFERENCES machine_types(machine_type_id)
);

--------------------------------------------------------------------------------
-- RAW TABLES (Messy)
-- These simulate real-world data with inconsistent formats and references.
-- String-based refs don't have FK constraints - that's intentional!
--------------------------------------------------------------------------------

-- Factory layout: machine positions with dirty references
CREATE TABLE IF NOT EXISTS layout_raw (
  layout_id INTEGER PRIMARY KEY,
  machine_ref_raw TEXT NOT NULL,
  zone_ref_raw TEXT NOT NULL,
  x REAL,
  y REAL,
  row_num INTEGER,
  col_num INTEGER,
  effective_from_raw TEXT NOT NULL
);

-- Shifts: schedule with dirty timestamps and supervisor refs
CREATE TABLE IF NOT EXISTS shifts_raw (
  shift_id INTEGER PRIMARY KEY,
  shift_code TEXT NOT NULL UNIQUE,      -- S-YYYYMMDD-{D|S|N}
  shift_name TEXT NOT NULL,             -- Day, Swing, Night
  shift_start_raw TEXT NOT NULL,
  shift_end_raw TEXT NOT NULL,
  supervisor_ref_raw TEXT,
  team_code TEXT,
  created_at_iso TEXT NOT NULL          -- clean ingestion timestamp
);

-- Shift assignments: who worked which shift, with dirty refs
CREATE TABLE IF NOT EXISTS shift_assignments_raw (
  assignment_id INTEGER PRIMARY KEY,
  shift_code TEXT NOT NULL,
  employee_ref_raw TEXT NOT NULL,
  role_ref_raw TEXT NOT NULL,
  clock_in_raw TEXT,
  clock_out_raw TEXT,
  created_at_iso TEXT NOT NULL
);

-- Incident reports: the core messy data
CREATE TABLE IF NOT EXISTS incident_reports_raw (
  incident_id INTEGER PRIMARY KEY,
  incident_time_raw TEXT NOT NULL,
  reported_time_raw TEXT NOT NULL,
  shift_code_ref_raw TEXT,
  employee_ref_raw TEXT,
  machine_ref_raw TEXT,
  zone_ref_raw TEXT,
  incident_type_raw TEXT NOT NULL,
  severity_raw TEXT NOT NULL,
  description TEXT,
  created_at_iso TEXT NOT NULL
);

-- Maintenance logs: repair records with dirty refs
CREATE TABLE IF NOT EXISTS maintenance_logs_raw (
  maintenance_id INTEGER PRIMARY KEY,
  machine_ref_raw TEXT NOT NULL,
  maint_start_raw TEXT NOT NULL,
  maint_end_raw TEXT,
  maint_type_raw TEXT NOT NULL,
  notes TEXT,
  created_at_iso TEXT NOT NULL
);

--------------------------------------------------------------------------------
-- INDEXES
-- Even with raw/dirty fields, indexes help query performance.
--------------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_shifts_raw_shift_code ON shifts_raw(shift_code);
CREATE INDEX IF NOT EXISTS idx_assignments_raw_shift_code ON shift_assignments_raw(shift_code);
CREATE INDEX IF NOT EXISTS idx_incidents_raw_shift_code ON incident_reports_raw(shift_code_ref_raw);
CREATE INDEX IF NOT EXISTS idx_incidents_raw_machine_ref ON incident_reports_raw(machine_ref_raw);
CREATE INDEX IF NOT EXISTS idx_incidents_raw_employee_ref ON incident_reports_raw(employee_ref_raw);
