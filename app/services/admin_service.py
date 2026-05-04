from __future__ import annotations

import bcrypt

import db.settings_dal as _settings_dal
from app.constants import KNOWN_SETTINGS_KEYS
from app.exceptions import InvalidPinError, PinNotSetError


def set_pin(new_pin: str) -> None:
    """Hashes new_pin with bcrypt and stores the hash in AppSettings."""
    hashed = bcrypt.hashpw(new_pin.encode(), bcrypt.gensalt()).decode()
    _settings_dal.set_setting("admin_pin", hashed)


def verify_pin(pin: str) -> bool:
    """
    Returns True if pin matches the stored bcrypt hash.
    Raises PinNotSetError if no PIN has been configured yet.
    """
    stored = _settings_dal.get_setting("admin_pin")
    if not stored:
        raise PinNotSetError()
    return bcrypt.checkpw(pin.encode(), stored.encode())


def require_pin(pin: str) -> None:
    """
    Convenience guard — raises InvalidPinError on mismatch.
    Use at the start of any PIN-gated service call.
    """
    if not verify_pin(pin):
        raise InvalidPinError()


def change_pin(current_pin: str, new_pin: str) -> None:
    """
    Verifies the current PIN before setting a new one.
    Raises InvalidPinError if the current PIN is wrong.
    """
    require_pin(current_pin)
    set_pin(new_pin)


def pin_is_set() -> bool:
    """Returns True if an admin PIN has been configured."""
    return bool(_settings_dal.get_setting("admin_pin"))


def get_all_settings() -> dict[str, str]:
    """
    Returns all AppSettings rows as a dict, excluding the admin_pin hash
    (which must never be exposed to the UI layer).
    """
    result: dict[str, str] = {}
    for key in KNOWN_SETTINGS_KEYS:
        if key == "admin_pin":
            continue
        val = _settings_dal.get_setting(key)
        if val is not None:
            result[key] = val
    return result


def update_threshold(key: str, value: str) -> None:
    """
    Updates a configurable threshold. Validates that the key is a known
    threshold before writing — refuses unknown keys.
    """
    editable_keys = KNOWN_SETTINGS_KEYS - {"admin_pin", "current_mode"}
    if key not in editable_keys:
        raise ValueError(f"'{key}' is not a configurable threshold key.")
    _settings_dal.set_setting(key, value)
