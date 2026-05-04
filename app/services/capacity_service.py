from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import db.capacity_dal as _dal
import db.battery_dal as _bat_dal
from app.exceptions import BatteryNotFoundError


@dataclass
class CapacityTestDTO:
    test_id: int
    battery_id: int
    test_date: datetime
    capacity_ah: float


def _to_dto(row: _dal.CapacityTestRow) -> CapacityTestDTO:
    return CapacityTestDTO(
        test_id=row.test_id,
        battery_id=row.battery_id,
        test_date=row.test_date,
        capacity_ah=row.capacity_ah,
    )


def record_capacity_test(battery_id: int, capacity_ah: float) -> CapacityTestDTO:
    if _bat_dal.get_battery(battery_id) is None:
        raise BatteryNotFoundError(battery_id)
    test_id = _dal.insert_capacity_test(battery_id, capacity_ah)
    tests = _dal.get_capacity_tests(battery_id)
    match = next(t for t in tests if t.test_id == test_id)
    return _to_dto(match)


def get_capacity_tests(battery_id: int) -> list[CapacityTestDTO]:
    if _bat_dal.get_battery(battery_id) is None:
        raise BatteryNotFoundError(battery_id)
    return [_to_dto(r) for r in _dal.get_capacity_tests(battery_id)]
