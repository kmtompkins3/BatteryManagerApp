from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

import db.battery_dal as _dal
from app.exceptions import (
    BatteryAlreadyRetiredError,
    BatteryNotBrokenInError,
    BatteryNotFoundError,
)


@dataclass
class BatteryDTO:
    battery_id: int
    brand: str
    batch_number: str
    broken_in: bool
    purchase_date: Optional[date]
    date_added: datetime
    retired: bool


def _to_dto(row: _dal.BatteryRow) -> BatteryDTO:
    return BatteryDTO(
        battery_id=row.battery_id,
        brand=row.brand,
        batch_number=row.batch_number,
        broken_in=row.broken_in,
        purchase_date=row.purchase_date,
        date_added=row.date_added,
        retired=row.retired,
    )


def add_battery(
    brand: str,
    batch_number: str,
    broken_in: bool,
    purchase_date: Optional[date] = None,
) -> BatteryDTO:
    """
    Validates broken_in=True before writing.
    Raises BatteryNotBrokenInError if False.
    Returns full DTO with auto-assigned battery_id and date_added.
    """
    if not broken_in:
        raise BatteryNotBrokenInError()

    battery_id = _dal.insert_battery(brand, batch_number, broken_in, purchase_date)
    row = _dal.get_battery(battery_id)
    return _to_dto(row)


def get_battery(battery_id: int) -> BatteryDTO:
    """Raises BatteryNotFoundError if absent."""
    row = _dal.get_battery(battery_id)
    if row is None:
        raise BatteryNotFoundError(battery_id)
    return _to_dto(row)


def list_active_batteries() -> list[BatteryDTO]:
    return [_to_dto(r) for r in _dal.list_active_batteries()]


def list_all_batteries() -> list[BatteryDTO]:
    return [_to_dto(r) for r in _dal.list_all_batteries()]


def update_battery(
    battery_id: int,
    brand: str,
    batch_number: str,
    purchase_date: Optional[date] = None,
) -> BatteryDTO:
    """
    Updates editable fields. Battery ID and date_added are read-only.
    PIN enforcement must be done by the caller before invoking this.
    Raises BatteryNotFoundError if battery does not exist.
    """
    row = _dal.get_battery(battery_id)
    if row is None:
        raise BatteryNotFoundError(battery_id)
    _dal.update_battery(battery_id, brand, batch_number, purchase_date)
    return get_battery(battery_id)


def retire_battery(battery_id: int) -> None:
    """
    Sets retired=True.
    Raises BatteryNotFoundError if absent.
    Raises BatteryAlreadyRetiredError if already retired.
    PIN enforcement must be done by the caller.
    """
    row = _dal.get_battery(battery_id)
    if row is None:
        raise BatteryNotFoundError(battery_id)
    if row.retired:
        raise BatteryAlreadyRetiredError(battery_id)
    _dal.set_retired(battery_id, True)
