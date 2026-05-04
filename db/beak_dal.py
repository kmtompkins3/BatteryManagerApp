from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from db.connection import get_db


@dataclass
class BeakReadingRow:
    reading_id: int
    session_id: int
    battery_id: int
    voltage: float
    charge_pct: int
    resistance_mohm: float


def _row_to_beak(row) -> BeakReadingRow:
    return BeakReadingRow(
        reading_id=row["reading_id"],
        session_id=row["session_id"],
        battery_id=row["battery_id"],
        voltage=row["voltage"],
        charge_pct=row["charge_pct"],
        resistance_mohm=row["resistance_mohm"],
    )


def insert_beak_reading(
    session_id: int,
    battery_id: int,
    voltage: float,
    charge_pct: int,
    resistance_mohm: float,
) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO BeakReading (session_id, battery_id, voltage, charge_pct, resistance_mohm)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, battery_id, round(voltage, 2), charge_pct, resistance_mohm),
        )
        return cur.lastrowid


def get_readings_for_battery(battery_id: int) -> list[BeakReadingRow]:
    """Returns readings ordered by session scan_out_time ascending (for graph X-axis)."""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT br.*
            FROM BeakReading br
            JOIN Session s ON br.session_id = s.session_id
            WHERE br.battery_id = ?
            ORDER BY s.scan_out_time ASC
            """,
            (battery_id,),
        ).fetchall()
    return [_row_to_beak(r) for r in rows]


def get_reading_for_session(session_id: int) -> Optional[BeakReadingRow]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM BeakReading WHERE session_id = ?", (session_id,)
        ).fetchone()
    return _row_to_beak(row) if row else None
