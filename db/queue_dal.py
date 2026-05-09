from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from db.connection import get_db


@dataclass
class QueueRow:
    queue_position: int
    battery_id: int
    status: str
    scan_out_time: Optional[datetime]
    cooling_start_time: Optional[datetime]
    missing_since: Optional[datetime]


def _row_to_queue(row) -> QueueRow:
    return QueueRow(
        queue_position=row["queue_position"],
        battery_id=row["battery_id"],
        status=row["status"],
        scan_out_time=(
            datetime.fromisoformat(row["scan_out_time"]) if row["scan_out_time"] else None
        ),
        cooling_start_time=(
            datetime.fromisoformat(row["cooling_start_time"])
            if row["cooling_start_time"]
            else None
        ),
        missing_since=(
            datetime.fromisoformat(row["missing_since"]) if row["missing_since"] else None
        ),
    )


def init_queue(battery_ids: list[int]) -> None:
    """Clears all existing queue rows and inserts fresh rows in given order."""
    with get_db() as conn:
        conn.execute("DELETE FROM CompetitionQueue")
        for position, bid in enumerate(battery_ids):
            conn.execute(
                """
                INSERT INTO CompetitionQueue (queue_position, battery_id, status)
                VALUES (?, ?, 'Available')
                """,
                (position, bid),
            )


def get_queue() -> list[QueueRow]:
    """
    Returns all rows ordered so Missing batteries are pinned last,
    then by queue_position ascending for the rest.
    """
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM CompetitionQueue
            ORDER BY
                CASE WHEN status = 'Missing' THEN 1 ELSE 0 END ASC,
                queue_position ASC
            """
        ).fetchall()
    return [_row_to_queue(r) for r in rows]


def get_front_of_queue() -> Optional[QueueRow]:
    """First non-Missing row by queue_position."""
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT * FROM CompetitionQueue
            WHERE status != 'Missing'
            ORDER BY queue_position ASC
            LIMIT 1
            """
        ).fetchone()
    return _row_to_queue(row) if row else None


def get_queue_row(battery_id: int) -> Optional[QueueRow]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM CompetitionQueue WHERE battery_id = ?", (battery_id,)
        ).fetchone()
    return _row_to_queue(row) if row else None


def update_status(battery_id: int, status: str) -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE CompetitionQueue SET status = ? WHERE battery_id = ?",
            (status, battery_id),
        )


def set_scan_out_time(battery_id: int, scan_out_time: datetime) -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE CompetitionQueue SET scan_out_time = ? WHERE battery_id = ?",
            (scan_out_time.isoformat(), battery_id),
        )


def set_cooling_start_time(battery_id: int, cooling_start_time: datetime) -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE CompetitionQueue SET cooling_start_time = ? WHERE battery_id = ?",
            (cooling_start_time.isoformat(), battery_id),
        )


def clear_cooling_start_time(battery_id: int) -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE CompetitionQueue SET cooling_start_time = NULL WHERE battery_id = ?",
            (battery_id,),
        )


def set_missing_since(battery_id: int, missing_since: datetime) -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE CompetitionQueue SET missing_since = ? WHERE battery_id = ?",
            (missing_since.isoformat(), battery_id),
        )


def move_to_back(battery_id: int) -> None:
    """Assigns queue_position = max(current positions) + 1."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT MAX(queue_position) as max_pos FROM CompetitionQueue"
        ).fetchone()
        max_pos = row["max_pos"] if row["max_pos"] is not None else -1
        conn.execute(
            "UPDATE CompetitionQueue SET queue_position = ? WHERE battery_id = ?",
            (max_pos + 1, battery_id),
        )


def pin_to_bottom_missing(battery_id: int) -> None:
    """Sets status = Missing. get_queue() handles display order via SQL ORDER BY."""
    with get_db() as conn:
        conn.execute(
            "UPDATE CompetitionQueue SET status = 'Missing' WHERE battery_id = ?",
            (battery_id,),
        )


def add_to_queue(battery_id: int) -> None:
    """Adds a single battery at the end of the queue with status Available."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT MAX(queue_position) as max_pos FROM CompetitionQueue"
        ).fetchone()
        next_pos = (row["max_pos"] + 1) if row["max_pos"] is not None else 0
        conn.execute(
            """
            INSERT OR IGNORE INTO CompetitionQueue (queue_position, battery_id, status)
            VALUES (?, ?, 'Available')
            """,
            (next_pos, battery_id),
        )


def remove_from_queue(battery_id: int) -> None:
    with get_db() as conn:
        conn.execute(
            "DELETE FROM CompetitionQueue WHERE battery_id = ?", (battery_id,)
        )


def clear_queue() -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM CompetitionQueue")


def set_all_statuses_available() -> None:
    with get_db() as conn:
        conn.execute("UPDATE CompetitionQueue SET status = 'Available'")
