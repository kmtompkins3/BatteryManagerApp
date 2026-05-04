from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from db.connection import get_db


@dataclass
class OverrideLogRow:
    log_id: int
    timestamp: datetime
    battery_id: int
    action_description: str


def _row_to_override(row) -> OverrideLogRow:
    return OverrideLogRow(
        log_id=row["log_id"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        battery_id=row["battery_id"],
        action_description=row["action_description"],
    )


def insert_override_log(battery_id: int, action_description: str) -> int:
    now = datetime.now().isoformat()
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO OverrideLog (timestamp, battery_id, action_description)
            VALUES (?, ?, ?)
            """,
            (now, battery_id, action_description),
        )
        return cur.lastrowid


def get_all_override_logs() -> list[OverrideLogRow]:
    """Ordered by timestamp descending."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM OverrideLog ORDER BY timestamp DESC"
        ).fetchall()
    return [_row_to_override(r) for r in rows]
