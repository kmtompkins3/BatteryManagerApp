from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import db.session_dal as _session_dal
import db.beak_dal as _beak_dal
import db.battery_dal as _bat_dal
import db.queue_dal as _queue_dal
import db.override_dal as _override_dal
from app.constants import BatteryStatus, PRACTICE_MAX_SESSION_HOURS
from app.exceptions import (
    BatteryNotFoundError,
    NoOpenSessionError,
    SessionAlreadyOpenError,
)


@dataclass
class SessionDTO:
    session_id: int
    battery_id: int
    scan_out_time: datetime
    scan_in_time: Optional[datetime]
    duration_minutes: Optional[float]
    override_used: bool


def _to_dto(row: _session_dal.SessionRow) -> SessionDTO:
    return SessionDTO(
        session_id=row.session_id,
        battery_id=row.battery_id,
        scan_out_time=row.scan_out_time,
        scan_in_time=row.scan_in_time,
        duration_minutes=row.duration_minutes,
        override_used=row.override_used,
    )


# ── Practice Mode ─────────────────────────────────────────────────────────────

def scan_out_practice(
    battery_id: int,
    voltage: float,
    charge_pct: int,
    resistance_mohm: float,
    force: bool = False,
) -> SessionDTO:
    """
    Opens a scan-out session for Practice mode.

    If the battery already has an open session and force=False, raises
    SessionAlreadyOpenError. If force=True, logs override, nulls old session
    duration, and starts a fresh session (override_used=True on the new one).

    Always requires beak readings.
    """
    if _bat_dal.get_battery(battery_id) is None:
        raise BatteryNotFoundError(battery_id)

    existing = _session_dal.get_open_session_for_battery(battery_id)
    if existing:
        if not force:
            raise SessionAlreadyOpenError(battery_id, existing.session_id)
        # Force: log override, close stale session with current time
        _override_dal.insert_override_log(
            battery_id,
            f"Force reset of open session {existing.session_id} on scan-out (Practice mode).",
        )
        _session_dal.close_session(existing.session_id, datetime.now())

    now = datetime.now()
    session_id = _session_dal.insert_session(battery_id, now, override_used=force)
    _beak_dal.insert_beak_reading(session_id, battery_id, voltage, charge_pct, resistance_mohm)

    row = _session_dal.get_open_session_for_battery(battery_id)
    return _to_dto(row)


def scan_in_practice(battery_id: int, force: bool = False) -> SessionDTO:
    """
    Closes the open session for Practice mode.

    If no open session exists and force=False, raises NoOpenSessionError.
    If force=True, creates a zero-duration override session.

    If the session duration exceeds PRACTICE_MAX_SESSION_HOURS, duration_minutes
    is set to NULL (discarded) but the BeakReading is retained.
    """
    if _bat_dal.get_battery(battery_id) is None:
        raise BatteryNotFoundError(battery_id)

    existing = _session_dal.get_open_session_for_battery(battery_id)
    now = datetime.now()

    if existing is None:
        if not force:
            raise NoOpenSessionError(battery_id)
        # Force: create a zero-duration override session that is immediately closed
        _override_dal.insert_override_log(
            battery_id,
            f"Force scan-in for battery {battery_id} with no open session (Practice mode).",
        )
        session_id = _session_dal.insert_session(battery_id, now, override_used=True)
        _session_dal.close_session(session_id, now)
        row = next(
            s for s in _session_dal.get_sessions_for_battery(battery_id)
            if s.session_id == session_id
        )
        return _to_dto(row)

    _session_dal.close_session(existing.session_id, now)

    # Check >3h rule
    elapsed_hours = (now - existing.scan_out_time).total_seconds() / 3600
    if elapsed_hours > PRACTICE_MAX_SESSION_HOURS:
        _session_dal.set_duration_null(existing.session_id)

    row = next(
        s for s in _session_dal.get_sessions_for_battery(battery_id)
        if s.session_id == existing.session_id
    )
    return _to_dto(row)


# ── Competition Mode ──────────────────────────────────────────────────────────

def scan_out_competition(
    battery_id: int,
    voltage: float,
    charge_pct: int,
    resistance_mohm: float,
    override: bool = False,
) -> SessionDTO:
    """
    Opens a competition scan-out session.

    FIFO enforcement is done by competition_service.assert_front_of_queue()
    before calling here. This function assumes the caller has already checked
    (or overridden) queue order.

    If override=True, sets override_used=True and logs to OverrideLog.
    """
    if _bat_dal.get_battery(battery_id) is None:
        raise BatteryNotFoundError(battery_id)

    if override:
        _override_dal.insert_override_log(
            battery_id,
            f"Override scan-out for battery {battery_id} (not front of competition queue).",
        )

    now = datetime.now()
    session_id = _session_dal.insert_session(battery_id, now, override_used=override)
    _beak_dal.insert_beak_reading(session_id, battery_id, voltage, charge_pct, resistance_mohm)

    _queue_dal.update_status(battery_id, BatteryStatus.ON_FIELD.value)
    _queue_dal.set_scan_out_time(battery_id, now)

    row = _session_dal.get_open_session_for_battery(battery_id)
    return _to_dto(row)


def scan_in_competition(battery_id: int) -> SessionDTO:
    """
    Closes the competition scan-in session, sets status to Cooling,
    records cooling_start_time, and moves battery to back of queue.
    """
    if _bat_dal.get_battery(battery_id) is None:
        raise BatteryNotFoundError(battery_id)

    existing = _session_dal.get_open_session_for_battery(battery_id)
    if existing is None:
        raise NoOpenSessionError(battery_id)

    now = datetime.now()
    _session_dal.close_session(existing.session_id, now)
    _queue_dal.update_status(battery_id, BatteryStatus.COOLING.value)
    _queue_dal.set_cooling_start_time(battery_id, now)
    _queue_dal.move_to_back(battery_id)

    row = next(
        s for s in _session_dal.get_sessions_for_battery(battery_id)
        if s.session_id == existing.session_id
    )
    return _to_dto(row)
