"""
data_helpers.py

Shared constants and helper functions for generating "dirty" factory data.
These utilities create realistic data quality issues for the training exercise.

NOTE: This module is intentionally in util/ to keep it separate from the
exercise materials. Students should not need to look at this code.
"""

import random
from datetime import datetime
from typing import Dict, List, Optional


# =============================================================================
# DATE FORMATS
# Multiple formats to simulate inconsistent data entry systems
# =============================================================================

DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S",  # 2024-03-15 14:32:45
    "%Y-%m-%d %H:%M",  # 2024-03-15 14:32
    "%Y-%m-%d %H",  # 2024-03-15 14 (missing minutes)
    "%Y-%m-%d",  # 2024-03-15 (date only)
    "%m/%d/%Y %H:%M:%S",  # 03/15/2024 14:32:45 (US format)
    "%m/%d/%Y %H:%M",  # 03/15/2024 14:32
    "%m/%d/%Y",  # 03/15/2024
    "%d-%b-%Y %H:%M:%S",  # 15-Mar-2024 14:32:45
    "%d-%b-%Y %H:%M",  # 15-Mar-2024 14:32
]


# =============================================================================
# SHIFT DEFINITIONS
# (name, start_hour, end_hour, code_suffix)
# =============================================================================

SHIFT_DEFS = [
    ("Day", 6, 14, "D"),
    ("Swing", 14, 22, "S"),
    ("Night", 22, 6, "N"),  # spans midnight
]


# =============================================================================
# INCIDENT TYPE VARIANTS
# Maps canonical type -> list of messy representations
# =============================================================================

INCIDENT_TYPE_VARIANTS: Dict[str, List[str]] = {
    "machine_failure": [
        "Machine Failure",
        "machine_fail",
        "MECH_FAIL",
        "Mach failure",
        "machine failure ",  # trailing space
    ],
    "safety_violation": [
        "Safety Violation",
        "SAFETY_VIOL",
        "safety-violation",
        "Safety vio.",
    ],
    "near_miss": [
        "Near Miss",
        "near-miss",
        "NEAR_MISS",
        "Nearmiss",
    ],
    "injury_minor": [
        "Minor Injury",
        "injury_minor",
        "MIN_INJ",
        "Minor inj.",
    ],
    "injury_major": [
        "Major Injury",
        "injury_major",
        "MAJ_INJ",
        "Major inj.",
    ],
    "quality_defect": [
        "Quality Defect",
        "quality_defect",
        "QA_DEFECT",
        "Quality issue",
    ],
    "power_event": [
        "Power Event",
        "power_event",
        "PWR_EVT",
        "Power fluctuation",
    ],
    "unknown": [
        "Unknown",
        "UNK",
        "?",
        "n/a",
    ],
}


# =============================================================================
# SEVERITY VARIANTS
# Maps canonical severity -> list of messy representations
# =============================================================================

SEVERITY_VARIANTS: Dict[str, List[str]] = {
    "low": ["low", "LOW", "1", "sev1", "minor", "L"],
    "medium": ["medium", "MED", "2", "sev2", "moderate", "M"],
    "high": ["high", "HIGH", "3", "sev3", "major", "H"],
    "critical": ["critical", "CRIT", "4", "sev4", "catastrophic", "C"],
}


# =============================================================================
# ROLE VARIANTS
# Inconsistent role naming in shift assignments
# =============================================================================

ROLE_VARIANTS = [
    "Operator",
    "OPR",
    "Tech",
    "Technician",
    "Supervisor",
    "Supv",
    "Quality",
    "QA",
    "Maintenance",
    "Maint",
]


# =============================================================================
# MAINTENANCE TYPE VARIANTS
# =============================================================================

MAINT_TYPE_VARIANTS = [
    "Preventive",
    "PREV",
    "Corrective",
    "CORR",
    "Inspection",
    "INSP",
    "Emergency",
    "EMERG",
]


# =============================================================================
# OUTLIER CONFIGURATION
# These settings control which machines/employees are "bad actors"
# =============================================================================

# Specific machines that should have high incident rates
BAD_MACHINE_CODES = ["M-003", "M-017", "M-024"]

# Weight multiplier for bad machines when selecting incident machine
BAD_MACHINE_WEIGHT = 4.0

# Weight multiplier for bad employees when selecting incident employee
BAD_EMPLOYEE_WEIGHT = 3.5

# Number of random employees to mark as "bad actors"
NUM_BAD_EMPLOYEES = 4

# Machine type incident rate multipliers
MACHINE_TYPE_MULTIPLIER: Dict[str, float] = {
    "Press": 1.9,
    "Conveyor": 1.6,
    "LaserCutter": 1.3,
    "CNC": 1.2,
    "Mixer": 1.1,
    "RobotArm": 1.05,
}

# Shift risk multipliers
SHIFT_RISK: Dict[str, float] = {
    "D": 1.0,
    "S": 1.15,
    "N": 1.45,
}

# Base expected incidents per shift (Poisson lambda)
# Tuned to yield ~400-600 incidents over ~2200 shifts
BASE_INCIDENT_LAMBDA = 0.08


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


# Fixed reference date for created_at fields (ensures reproducible DB)
# Set to a date after the typical data range (2024-01-01 to 2025-12-31)
FIXED_CREATED_AT = datetime(2026, 1, 15, 12, 0, 0)


def iso_now(dt: Optional[datetime] = None) -> str:
    """Return ISO timestamp string (for created_at fields).

    Uses a fixed reference date by default to ensure reproducible database creation.
    """
    return (dt or FIXED_CREATED_AT).replace(microsecond=0).isoformat()


def dirty_dt(dt: datetime, rng: random.Random) -> str:
    """
    Render datetime into a dirty string with random format and noise.

    Introduces:
    - Random date format selection
    - 8% chance of leading/trailing whitespace
    - 10% chance of time truncation
    - 5% chance of dropping time entirely
    """
    fmt = rng.choice(DATE_FORMATS)
    s = dt.strftime(fmt)

    # Add extra whitespace occasionally
    if rng.random() < 0.08:
        s = f" {s} "

    # Occasionally drop minutes/seconds by truncation
    if rng.random() < 0.10:
        if " " in s:
            parts = s.strip().split(" ")
            if len(parts) >= 2:
                s = parts[0] + " " + parts[1].split(":")[0]

    # Occasionally remove time portion entirely
    if rng.random() < 0.05:
        s = s.strip().split(" ")[0]

    return s


def dirty_machine_ref(machine_code: str, rng: random.Random) -> str:
    """
    Generate inconsistent machine reference from canonical code (e.g., 'M-017').

    Variants include: M-017, m-017, M017, 017, Machine 017, M17, MX-017, etc.
    """
    digits = "".join(ch for ch in machine_code if ch.isdigit())
    variants = [
        machine_code,
        machine_code.lower(),
        machine_code.replace("-", ""),
        digits,  # just the number
        f"Machine {digits}",
        f"M{digits}",
        f" M-{digits} ",  # extra spaces
        f"MX-{digits}" if rng.random() < 0.15 else machine_code,  # wrong prefix
    ]
    return rng.choice(variants)


def dirty_employee_ref(
    employee_id: int, badge_id: str, full_name: str, rng: random.Random
) -> str:
    """
    Generate inconsistent employee reference.

    Variants include: badge_id, EMP-id, full name, uppercase name, etc.
    6% chance of bogus/non-existent reference.
    """
    variants = [
        badge_id,
        badge_id.lower(),
        f"EMP-{employee_id}",
        str(employee_id),
        full_name,
        f"{full_name.upper()}",
        f" {badge_id} ",
        f"Badge:{badge_id}",
    ]

    # Occasionally generate non-existent or malformed reference
    if rng.random() < 0.06:
        return rng.choice(
            [
                f"B{rng.randint(9000, 9999)}",
                f"EMP-{rng.randint(9000, 9999)}",
                "UNKNOWN",
                "",
                "n/a",
            ]
        )

    return rng.choice(variants)


def dirty_zone_ref(zone_code: str, rng: random.Random) -> str:
    """
    Generate inconsistent zone reference.

    3% chance of bogus zone reference.
    """
    variants = [
        zone_code,
        zone_code.lower(),
        zone_code.replace("-", ""),
        f"Zone {zone_code}",
        f" {zone_code} ",
    ]

    # Occasional wrong zone
    if rng.random() < 0.03:
        return rng.choice(["Z-99", "ZONE-UNKNOWN", ""])

    return rng.choice(variants)


def pick_variant(
    mapping: Dict[str, List[str]], canonical_key: str, rng: random.Random
) -> str:
    """Pick a random variant for a canonical value."""
    return rng.choice(mapping[canonical_key])


def maybe_typo(s: str, rng: random.Random) -> str:
    """
    Introduce small typos with 6% probability.
    Swaps two adjacent characters.
    """
    if not s or rng.random() > 0.06 or len(s) < 4:
        return s

    i = rng.randint(0, len(s) - 2)
    lst = list(s)
    lst[i], lst[i + 1] = lst[i + 1], lst[i]
    return "".join(lst)


def make_shift_code(day: datetime, suffix: str) -> str:
    """Generate shift code like S-20240115-D."""
    return f"S-{day.strftime('%Y%m%d')}-{suffix}"


def choose_incident_type_for_machine(machine_type: str, rng: random.Random) -> str:
    """
    Choose canonical incident type weighted by machine type.

    Different machine types have different incident profiles:
    - Press: more machine failures and minor injuries
    - Conveyor: more machine failures and near misses
    - LaserCutter: more quality defects and safety violations
    """
    base = [
        ("machine_failure", 0.45),
        ("quality_defect", 0.15),
        ("near_miss", 0.15),
        ("safety_violation", 0.10),
        ("power_event", 0.05),
        ("injury_minor", 0.08),
        ("injury_major", 0.02),
    ]

    # Machine-type specific bias
    if machine_type == "Press":
        bump = {"machine_failure": 0.15, "injury_minor": 0.05}
    elif machine_type == "Conveyor":
        bump = {"machine_failure": 0.12, "near_miss": 0.06}
    elif machine_type == "LaserCutter":
        bump = {"quality_defect": 0.10, "safety_violation": 0.06}
    else:
        bump = {}

    # Apply bumps and renormalize
    keys, weights = [], []
    for k, w in base:
        keys.append(k)
        weights.append(max(0.001, w + bump.get(k, 0.0)))

    total = sum(weights)
    weights = [w / total for w in weights]

    return rng.choices(keys, weights=weights, k=1)[0]


def choose_severity(canonical_type: str, rng: random.Random) -> str:
    """
    Choose canonical severity based on incident type.

    - injury_major: 70% high, 30% critical
    - machine_failure: 55% medium, 45% high
    - safety_violation, power_event: 25% low, 55% medium, 20% high
    - others: 70% low, 30% medium
    """
    if canonical_type in ("injury_major",):
        return rng.choices(["high", "critical"], weights=[0.7, 0.3], k=1)[0]
    elif canonical_type in ("machine_failure",):
        return rng.choices(["medium", "high"], weights=[0.55, 0.45], k=1)[0]
    elif canonical_type in ("safety_violation", "power_event"):
        return rng.choices(["low", "medium", "high"], weights=[0.25, 0.55, 0.20], k=1)[
            0
        ]
    else:
        return rng.choices(["low", "medium"], weights=[0.7, 0.3], k=1)[0]


# =============================================================================
# SEED DATA
# Reference data for clean tables
# =============================================================================

MACHINE_TYPES_SEED = [
    ("Press", "forming", 650),
    ("CNC", "machining", 900),
    ("Conveyor", "material_handling", 500),
    ("RobotArm", "assembly", 1200),
    ("LaserCutter", "cutting", 800),
    ("Mixer", "processing", 700),
]

INCIDENT_TYPES_SEED = [
    ("machine_failure", "equipment", "high"),
    ("safety_violation", "safety", "medium"),
    ("near_miss", "safety", "low"),
    ("injury_minor", "safety", "medium"),
    ("injury_major", "safety", "high"),
    ("quality_defect", "quality", "low"),
    ("power_event", "facility", "medium"),
    ("unknown", "other", "low"),
]

ZONES_SEED = [
    ("Z-01", "Inbound / Receiving"),
    ("Z-02", "Machining Bay"),
    ("Z-03", "Assembly Line"),
    ("Z-04", "Packaging"),
    ("Z-05", "Maintenance Corner"),
    ("Z-06", "Utilities / Power"),
]

FIRST_NAMES = [
    "Avery",
    "Jordan",
    "Casey",
    "Taylor",
    "Morgan",
    "Riley",
    "Quinn",
    "Cameron",
    "Drew",
    "Parker",
    "Alex",
    "Jamie",
    "Sam",
    "Robin",
    "Hayden",
    "Kendall",
    "Blake",
    "Skyler",
    "Reese",
    "Rowan",
]

LAST_NAMES = [
    "Nguyen",
    "Patel",
    "Garcia",
    "Smith",
    "Johnson",
    "Brown",
    "Davis",
    "Miller",
    "Wilson",
    "Moore",
    "Taylor",
    "Anderson",
    "Thomas",
    "Jackson",
    "White",
    "Harris",
    "Martin",
    "Thompson",
    "Lee",
    "Clark",
]

VENDORS = [
    "Apex Industrial",
    "NorthBridge Robotics",
    "CrownWorks",
    "OmniFab",
    "Kinetic Machines",
    "VectorForge",
]

INCIDENT_DESCRIPTIONS = [
    "Operator reported abnormal vibration and shutdown.",
    "Incident observed during routine QA check.",
    "Unexpected stop triggered by sensor.",
    "Guarding not fully engaged; corrected on site.",
    "Minor cut reported; first aid applied.",
    "Repeated jam; line paused for inspection.",
]

MAINTENANCE_NOTES = [
    "Replaced worn belt; tested OK.",
    "Lubricated bearings; reduced vibration.",
    "Adjusted alignment; cleared jam.",
    "Replaced sensor; recalibrated.",
    "Emergency stop circuit inspected.",
    "Scheduled maintenance window.",
]
