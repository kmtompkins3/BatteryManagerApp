from enum import Enum


class BatteryStatus(str, Enum):
    AVAILABLE = "Available"
    ON_FIELD  = "OnField"
    COOLING   = "Cooling"
    CHARGING  = "Charging"
    MISSING   = "Missing"
    RETIRED   = "Retired"


class AppMode(str, Enum):
    PRACTICE    = "Practice"
    COMPETITION = "Competition"


PRACTICE_MAX_SESSION_HOURS = 3

KNOWN_SETTINGS_KEYS = {
    "admin_pin",
    "practice_not_scanned_in_hours",
    "practice_not_used_months",
    "practice_not_tested_months",
    "practice_imbalance_uses",
    "comp_missing_minutes",
    "comp_imbalance_uses",
    "cooling_minutes",
    "current_mode",
}
