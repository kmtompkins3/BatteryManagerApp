from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import db.queue_dal as _queue_dal
import db.settings_dal as _settings_dal
from app.constants import BatteryStatus


@dataclass
class CoolingStatus:
    battery_id: int
    cooling_start_time: datetime
    elapsed_seconds: float
    is_complete: bool
    remaining_seconds: float


@dataclass
class MissingCandidate:
    battery_id: int
    scan_out_time: datetime
    on_field_minutes: float


def check_cooling_timers() -> list[CoolingStatus]:
    """
    On-demand check. Queries all CompetitionQueue rows with status = Cooling.
    Returns CoolingStatus for each, with is_complete=True for any that have elapsed.

    No DB writes — the caller (competition_service or UI polling) decides what to do.
    """
    cooling_minutes = _settings_dal.get_setting_int("cooling_minutes", 15)
    cooling_seconds = cooling_minutes * 60
    results: list[CoolingStatus] = []
    now = datetime.now()

    for row in _queue_dal.get_queue():
        if row.status != BatteryStatus.COOLING.value:
            continue
        if row.cooling_start_time is None:
            continue
        elapsed = (now - row.cooling_start_time).total_seconds()
        is_complete = elapsed >= cooling_seconds
        remaining = max(0.0, cooling_seconds - elapsed)
        results.append(
            CoolingStatus(
                battery_id=row.battery_id,
                cooling_start_time=row.cooling_start_time,
                elapsed_seconds=elapsed,
                is_complete=is_complete,
                remaining_seconds=remaining,
            )
        )
    return results


def check_missing_candidates() -> list[MissingCandidate]:
    """
    On-demand check. Returns OnField batteries whose scan_out_time exceeds
    the comp_missing_minutes threshold.

    No DB writes — caller calls competition_service.mark_missing() for each.
    """
    missing_minutes = _settings_dal.get_setting_int("comp_missing_minutes", 30)
    candidates: list[MissingCandidate] = []
    now = datetime.now()

    for row in _queue_dal.get_queue():
        if row.status != BatteryStatus.ON_FIELD.value:
            continue
        if row.scan_out_time is None:
            continue
        on_field_minutes = (now - row.scan_out_time).total_seconds() / 60.0
        if on_field_minutes >= missing_minutes:
            candidates.append(
                MissingCandidate(
                    battery_id=row.battery_id,
                    scan_out_time=row.scan_out_time,
                    on_field_minutes=on_field_minutes,
                )
            )
    return candidates


def get_cooling_remaining_seconds(battery_id: int) -> Optional[float]:
    """Single-battery convenience for UI countdown display."""
    cooling_minutes = _settings_dal.get_setting_int("cooling_minutes", 15)
    cooling_seconds = cooling_minutes * 60
    row = _queue_dal.get_queue_row(battery_id)
    if row is None or row.status != BatteryStatus.COOLING.value:
        return None
    if row.cooling_start_time is None:
        return None
    elapsed = (datetime.now() - row.cooling_start_time).total_seconds()
    return max(0.0, cooling_seconds - elapsed)
