from typing import Optional

from db.connection import get_db


def get_setting(key: str) -> Optional[str]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT value FROM AppSettings WHERE key = ?", (key,)
        ).fetchone()
    return row["value"] if row else None


def set_setting(key: str, value: str) -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO AppSettings (key, value) VALUES (?, ?)",
            (key, value),
        )


def get_setting_int(key: str, default: int = 0) -> int:
    val = get_setting(key)
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def get_setting_float(key: str, default: float = 0.0) -> float:
    val = get_setting(key)
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default
