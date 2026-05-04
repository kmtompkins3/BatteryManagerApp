from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from db.connection import get_db


@dataclass
class BatteryRow:
    battery_id: int
    brand: str
    batch_number: str
    broken_in: bool
    purchase_date: Optional[date]
    date_added: datetime
    retired: bool


def _row_to_battery(row) -> BatteryRow:
    return BatteryRow(
        battery_id=row["battery_id"],
        brand=row["brand"],
        batch_number=row["batch_number"],
        broken_in=bool(row["broken_in"]),
        purchase_date=(
            date.fromisoformat(row["purchase_date"]) if row["purchase_date"] else None
        ),
        date_added=datetime.fromisoformat(row["date_added"]),
        retired=bool(row["retired"]),
    )


def insert_battery(
    brand: str,
    batch_number: str,
    broken_in: bool,
    purchase_date: Optional[date],
) -> int:
    """Inserts a new battery and returns its auto-assigned battery_id."""
    now = datetime.now().isoformat()
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO Battery (brand, batch_number, broken_in, purchase_date, date_added, retired)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (
                brand,
                batch_number,
                int(broken_in),
                purchase_date.isoformat() if purchase_date else None,
                now,
            ),
        )
        return cur.lastrowid


def get_battery(battery_id: int) -> Optional[BatteryRow]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM Battery WHERE battery_id = ?", (battery_id,)
        ).fetchone()
    return _row_to_battery(row) if row else None


def list_active_batteries() -> list[BatteryRow]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM Battery WHERE retired = 0 ORDER BY battery_id"
        ).fetchall()
    return [_row_to_battery(r) for r in rows]


def list_all_batteries() -> list[BatteryRow]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM Battery ORDER BY battery_id"
        ).fetchall()
    return [_row_to_battery(r) for r in rows]


def update_battery(
    battery_id: int,
    brand: str,
    batch_number: str,
    purchase_date: Optional[date],
) -> None:
    with get_db() as conn:
        conn.execute(
            """
            UPDATE Battery
            SET brand = ?, batch_number = ?, purchase_date = ?
            WHERE battery_id = ?
            """,
            (
                brand,
                batch_number,
                purchase_date.isoformat() if purchase_date else None,
                battery_id,
            ),
        )


def set_retired(battery_id: int, retired: bool) -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE Battery SET retired = ? WHERE battery_id = ?",
            (int(retired), battery_id),
        )
