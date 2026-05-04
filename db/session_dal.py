from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from db.connection import get_db


@dataclass
class SessionRow:
    session_id: int
    battery_id: int
    scan_out_time: datetime
    scan_in_time: Optional[datetime]
    duration_minutes: Optional[float]
    override_used: bool


def _row_to_session(row) -> SessionRow:
    return SessionRow(
        session_id=row["session_id"],
        battery_id=row["battery_id"],
        scan_out_time=datetime.fromisoformat(row["scan_out_time"]),
        scan_in_time=(
            datetime.fromisoformat(row["scan_in_time"]) if row["scan_in_time"] else None
        ),
        duration_minutes=row["duration_minutes"],
        override_used=bool(row["override_used"]),
    )


def insert_session(
    battery_id: int,
    scan_out_time: datetime,
    override_used: bool = False,
) -> int:
    """Creates an open session (scan_in_time = NULL) and returns session_id."""
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO Session (battery_id, scan_out_time, override_used)
            VALUES (?, ?, ?)
            """,
            (battery_id, scan_out_time.isoformat(), int(override_used)),
        )
        return cur.lastrowid


def close_session(session_id: int, scan_in_time: datetime) -> None:
    """Sets scan_in_time and computes duration_minutes from elapsed wall-clock time."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT scan_out_time FROM Session WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row:
            scan_out = datetime.fromisoformat(row["scan_out_time"])
            duration = (scan_in_time - scan_out).total_seconds() / 60.0
            conn.execute(
                """
                UPDATE Session
                SET scan_in_time = ?, duration_minutes = ?
                WHERE session_id = ?
                """,
                (scan_in_time.isoformat(), duration, session_id),
            )


def set_duration_null(session_id: int) -> None:
    """Called when a Practice-mode session exceeded 3 hours — discards duration only."""
    with get_db() as conn:
        conn.execute(
            "UPDATE Session SET duration_minutes = NULL WHERE session_id = ?",
            (session_id,),
        )


def get_open_session_for_battery(battery_id: int) -> Optional[SessionRow]:
    """Returns the session with scan_in_time IS NULL, or None."""
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT * FROM Session
            WHERE battery_id = ? AND scan_in_time IS NULL
            ORDER BY scan_out_time DESC
            LIMIT 1
            """,
            (battery_id,),
        ).fetchone()
    return _row_to_session(row) if row else None


def get_sessions_for_battery(battery_id: int) -> list[SessionRow]:
    """Returns all sessions for a battery, most-recent first."""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM Session
            WHERE battery_id = ?
            ORDER BY scan_out_time DESC
            """,
            (battery_id,),
        ).fetchall()
    return [_row_to_session(r) for r in rows]


def get_total_uses(battery_id: int) -> int:
    """Count of closed sessions (scan_in_time IS NOT NULL)."""
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) as cnt FROM Session
            WHERE battery_id = ? AND scan_in_time IS NOT NULL
            """,
            (battery_id,),
        ).fetchone()
    return row["cnt"] if row else 0


def get_total_hours(battery_id: int) -> float:
    """Sum of non-null duration_minutes / 60, formatted to 1 decimal place."""
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(duration_minutes), 0) as total
            FROM Session
            WHERE battery_id = ? AND duration_minutes IS NOT NULL
            """,
            (battery_id,),
        ).fetchone()
    return round((row["total"] or 0) / 60.0, 1)


def get_last_scan_out_time(battery_id: int) -> Optional[datetime]:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT scan_out_time FROM Session
            WHERE battery_id = ?
            ORDER BY scan_out_time DESC
            LIMIT 1
            """,
            (battery_id,),
        ).fetchone()
    return datetime.fromisoformat(row["scan_out_time"]) if row else None


def get_min_uses_across_active_batteries() -> int:
    """Used for imbalance alert computation. Only counts non-retired batteries."""
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT MIN(use_count) as min_uses FROM (
                SELECT b.battery_id,
                       COUNT(s.session_id) as use_count
                FROM Battery b
                LEFT JOIN Session s
                  ON b.battery_id = s.battery_id AND s.scan_in_time IS NOT NULL
                WHERE b.retired = 0
                GROUP BY b.battery_id
            )
            """
        ).fetchone()
    return row["min_uses"] if row and row["min_uses"] is not None else 0
