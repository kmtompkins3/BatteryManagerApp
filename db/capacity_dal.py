from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from db.connection import get_db


@dataclass
class CapacityTestRow:
    test_id: int
    battery_id: int
    test_date: datetime
    capacity_ah: float


def _row_to_capacity(row) -> CapacityTestRow:
    return CapacityTestRow(
        test_id=row["test_id"],
        battery_id=row["battery_id"],
        test_date=datetime.fromisoformat(row["test_date"]),
        capacity_ah=row["capacity_ah"],
    )


def insert_capacity_test(battery_id: int, capacity_ah: float) -> int:
    now = datetime.now().isoformat()
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO CapacityTest (battery_id, test_date, capacity_ah) VALUES (?, ?, ?)",
            (battery_id, now, capacity_ah),
        )
        return cur.lastrowid


def get_capacity_tests(battery_id: int) -> list[CapacityTestRow]:
    """Ordered by test_date ascending (for graph X-axis)."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM CapacityTest WHERE battery_id = ? ORDER BY test_date ASC",
            (battery_id,),
        ).fetchall()
    return [_row_to_capacity(r) for r in rows]


def get_last_capacity_test_date(battery_id: int) -> Optional[datetime]:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT test_date FROM CapacityTest
            WHERE battery_id = ?
            ORDER BY test_date DESC
            LIMIT 1
            """,
            (battery_id,),
        ).fetchone()
    return datetime.fromisoformat(row["test_date"]) if row else None
