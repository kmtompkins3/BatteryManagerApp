from __future__ import annotations

from dataclasses import dataclass

import db.beak_dal as _dal
from app.exceptions import BatteryNotFoundError
import db.battery_dal as _bat_dal


@dataclass
class BeakReadingDTO:
    reading_id: int
    session_id: int
    battery_id: int
    voltage: float
    charge_pct: int
    resistance_mohm: float


def _to_dto(row: _dal.BeakReadingRow) -> BeakReadingDTO:
    return BeakReadingDTO(
        reading_id=row.reading_id,
        session_id=row.session_id,
        battery_id=row.battery_id,
        voltage=row.voltage,
        charge_pct=row.charge_pct,
        resistance_mohm=row.resistance_mohm,
    )


def save_beak_reading(
    session_id: int,
    battery_id: int,
    voltage: float,
    charge_pct: int,
    resistance_mohm: float,
) -> BeakReadingDTO:
    reading_id = _dal.insert_beak_reading(
        session_id, battery_id, voltage, charge_pct, resistance_mohm
    )
    row = _dal.get_reading_for_session(session_id)
    return _to_dto(row)


def get_readings_for_battery(battery_id: int) -> list[BeakReadingDTO]:
    if _bat_dal.get_battery(battery_id) is None:
        raise BatteryNotFoundError(battery_id)
    return [_to_dto(r) for r in _dal.get_readings_for_battery(battery_id)]
