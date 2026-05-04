from db.connection import get_db

_CREATE_BATTERY = """
CREATE TABLE IF NOT EXISTS Battery (
    battery_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    brand         TEXT    NOT NULL,
    batch_number  TEXT    NOT NULL,
    broken_in     INTEGER NOT NULL DEFAULT 0,
    purchase_date TEXT,
    date_added    TEXT    NOT NULL,
    retired       INTEGER NOT NULL DEFAULT 0
)
"""

_CREATE_SESSION = """
CREATE TABLE IF NOT EXISTS Session (
    session_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    battery_id       INTEGER NOT NULL REFERENCES Battery(battery_id),
    scan_out_time    TEXT    NOT NULL,
    scan_in_time     TEXT,
    duration_minutes REAL,
    override_used    INTEGER NOT NULL DEFAULT 0
)
"""

_CREATE_BEAK_READING = """
CREATE TABLE IF NOT EXISTS BeakReading (
    reading_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL REFERENCES Session(session_id),
    battery_id      INTEGER NOT NULL REFERENCES Battery(battery_id),
    voltage         REAL    NOT NULL,
    charge_pct      INTEGER NOT NULL,
    resistance_mohm REAL    NOT NULL
)
"""

_CREATE_CAPACITY_TEST = """
CREATE TABLE IF NOT EXISTS CapacityTest (
    test_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    battery_id  INTEGER NOT NULL REFERENCES Battery(battery_id),
    test_date   TEXT    NOT NULL,
    capacity_ah REAL    NOT NULL
)
"""

_CREATE_COMPETITION_QUEUE = """
CREATE TABLE IF NOT EXISTS CompetitionQueue (
    queue_position     INTEGER NOT NULL,
    battery_id         INTEGER NOT NULL UNIQUE REFERENCES Battery(battery_id),
    status             TEXT    NOT NULL DEFAULT 'Available',
    scan_out_time      TEXT,
    cooling_start_time TEXT,
    missing_since      TEXT
)
"""

_CREATE_OVERRIDE_LOG = """
CREATE TABLE IF NOT EXISTS OverrideLog (
    log_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp          TEXT    NOT NULL,
    battery_id         INTEGER NOT NULL,
    action_description TEXT    NOT NULL
)
"""

_CREATE_APP_SETTINGS = """
CREATE TABLE IF NOT EXISTS AppSettings (
    key   TEXT PRIMARY KEY,
    value TEXT
)
"""

_SEED_SETTINGS = [
    ("admin_pin",                     None),
    ("practice_not_scanned_in_hours", "2"),
    ("practice_not_used_months",      "1"),
    ("practice_not_tested_months",    "6"),
    ("practice_imbalance_uses",       "5"),
    ("comp_missing_minutes",          "30"),
    ("comp_imbalance_uses",           "1"),
    ("cooling_minutes",               "15"),
    ("current_mode",                  "Practice"),
]


def init_db() -> None:
    """
    Creates all tables (idempotent) and seeds AppSettings defaults.
    Safe to call on every app startup.
    """
    with get_db() as conn:
        conn.execute(_CREATE_BATTERY)
        conn.execute(_CREATE_SESSION)
        conn.execute(_CREATE_BEAK_READING)
        conn.execute(_CREATE_CAPACITY_TEST)
        conn.execute(_CREATE_COMPETITION_QUEUE)
        conn.execute(_CREATE_OVERRIDE_LOG)
        conn.execute(_CREATE_APP_SETTINGS)

        for key, value in _SEED_SETTINGS:
            conn.execute(
                "INSERT OR IGNORE INTO AppSettings (key, value) VALUES (?, ?)",
                (key, value),
            )
