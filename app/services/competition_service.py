from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import db.battery_dal as _bat_dal
import db.queue_dal as _queue_dal
import db.settings_dal as _settings_dal
from app.constants import AppMode, BatteryStatus
from app.exceptions import (
    CompetitionNotActiveError,
    QueueEmptyError,
    WrongBatteryError,
)
from app.state import AppState


@dataclass
class QueueEntryDTO:
    queue_position: int
    battery_id: int
    status: str
    scan_out_time: Optional[datetime]
    cooling_start_time: Optional[datetime]
    missing_since: Optional[datetime]


def _to_dto(row: _queue_dal.QueueRow) -> QueueEntryDTO:
    return QueueEntryDTO(
        queue_position=row.queue_position,
        battery_id=row.battery_id,
        status=row.status,
        scan_out_time=row.scan_out_time,
        cooling_start_time=row.cooling_start_time,
        missing_since=row.missing_since,
    )


def start_competition() -> None:
    """
    Clears any existing CompetitionQueue, populates it with all active
    (non-retired) batteries in default order, and switches to Competition mode.
    """
    batteries = _bat_dal.list_active_batteries()
    battery_ids = [b.battery_id for b in batteries]
    _queue_dal.init_queue(battery_ids)
    AppState().mode = AppMode.COMPETITION
    _settings_dal.set_setting("current_mode", AppMode.COMPETITION.value)


def end_competition() -> None:
    """
    Resets all queue battery statuses to Available, clears the queue,
    and returns to Practice mode. PIN enforcement is the caller's responsibility.
    """
    _queue_dal.set_all_statuses_available()
    _queue_dal.clear_queue()
    AppState().reset()
    _settings_dal.set_setting("current_mode", AppMode.PRACTICE.value)


def get_ordered_queue() -> list[QueueEntryDTO]:
    """Returns queue with Missing batteries pinned to the bottom."""
    if not AppState().is_competition:
        raise CompetitionNotActiveError()
    return [_to_dto(r) for r in _queue_dal.get_queue()]


def get_front_of_queue() -> Optional[QueueEntryDTO]:
    """Returns the first non-Missing row, or None if queue is empty."""
    row = _queue_dal.get_front_of_queue()
    return _to_dto(row) if row else None


def assert_front_of_queue(battery_id: int) -> None:
    """
    Raises WrongBatteryError if battery_id is not the front of the queue.
    Raises QueueEmptyError if no non-Missing batteries remain.
    """
    front = _queue_dal.get_front_of_queue()
    if front is None:
        raise QueueEmptyError()
    if front.battery_id != battery_id:
        raise WrongBatteryError(
            scanned_id=battery_id,
            correct_battery_id=front.battery_id,
        )


def confirm_cooling_complete(battery_id: int) -> None:
    """
    Called when the user presses 'Set to Charging' on a Cooling battery.
    Sets status = Charging and clears the cooling_start_time.
    """
    _queue_dal.update_status(battery_id, BatteryStatus.CHARGING.value)
    _queue_dal.clear_cooling_start_time(battery_id)


def mark_missing(battery_id: int) -> None:
    """
    Sets status = Missing, records missing_since timestamp, and pins to bottom of queue.
    Called by timer_service when a battery has been OnField past the threshold.
    """
    now = datetime.now()
    _queue_dal.update_status(battery_id, BatteryStatus.MISSING.value)
    _queue_dal.set_missing_since(battery_id, now)
    _queue_dal.pin_to_bottom_missing(battery_id)
