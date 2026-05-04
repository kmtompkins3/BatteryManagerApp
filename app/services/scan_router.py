from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import db.battery_dal as _bat_dal
import db.queue_dal as _queue_dal
from app.constants import AppMode, BatteryStatus
from app.exceptions import (
    BatteryNotFoundError,
    BatteryTrackerError,
    CompetitionNotActiveError,
    WrongBatteryError,
)
from app.state import AppState


@dataclass
class ScanResult:
    """
    Returned by handle_scan for every scan event.
    The UI inspects .error type to decide popup severity.
    No exception propagates past this boundary.
    """
    action_taken: str
    battery_id: int
    error: Optional[Exception] = field(default=None)
    data: Optional[Any] = field(default=None)


def handle_scan(raw_id: str) -> ScanResult:
    """
    Single entry point for all barcode scanner events.

    1. Parses raw_id to int.
    2. Validates battery exists and is not retired.
    3. Routes to the correct service based on AppState.mode and battery status.
    4. All exceptions are caught and returned in ScanResult.error — never re-raised.
    """
    # Parse raw ID
    try:
        battery_id = int(raw_id.strip())
    except (ValueError, AttributeError) as exc:
        return ScanResult(
            action_taken="invalid_id",
            battery_id=0,
            error=BatteryNotFoundError(0),
        )

    # Validate battery exists
    battery = _bat_dal.get_battery(battery_id)
    if battery is None:
        return ScanResult(
            action_taken="not_found",
            battery_id=battery_id,
            error=BatteryNotFoundError(battery_id),
        )

    if battery.retired:
        return ScanResult(
            action_taken="retired_battery",
            battery_id=battery_id,
            error=BatteryNotFoundError(battery_id),
        )

    mode = AppState().mode

    try:
        if mode == AppMode.PRACTICE:
            return _route_practice(battery_id)
        else:
            return _route_competition(battery_id)
    except BatteryTrackerError as exc:
        return ScanResult(
            action_taken="error",
            battery_id=battery_id,
            error=exc,
        )
    except Exception as exc:
        return ScanResult(
            action_taken="unexpected_error",
            battery_id=battery_id,
            error=exc,
        )


def _route_practice(battery_id: int) -> ScanResult:
    """Routes a Practice mode scan to scan_out or scan_in based on open session."""
    from app.services import session_service
    from db import session_dal as _s_dal

    open_session = _s_dal.get_open_session_for_battery(battery_id)

    if open_session is None:
        # Battery is Available — this is a scan-out attempt; UI must supply beak readings.
        # The router signals the UI that it needs to collect readings before proceeding.
        return ScanResult(
            action_taken="needs_beak_readings",
            battery_id=battery_id,
        )
    else:
        # Battery is OnField — let the UI decide: scan in or reset session start
        return ScanResult(
            action_taken="already_on_field",
            battery_id=battery_id,
        )


def _route_competition(battery_id: int) -> ScanResult:
    """Routes a Competition mode scan to the correct workflow."""
    from app.services import session_service
    from app.services import competition_service

    queue_row = _queue_dal.get_queue_row(battery_id)
    if queue_row is None:
        return ScanResult(
            action_taken="not_in_queue",
            battery_id=battery_id,
            error=CompetitionNotActiveError(),
        )

    status = queue_row.status

    if status == BatteryStatus.ON_FIELD.value or status == BatteryStatus.MISSING.value:
        # Scan-in (includes Missing batteries — normal workflow resumes)
        dto = session_service.scan_in_competition(battery_id)
        return ScanResult(
            action_taken="scan_in_competition",
            battery_id=battery_id,
            data=dto,
        )

    if status == BatteryStatus.AVAILABLE.value:
        # Scan-out attempt — check FIFO; signal UI to collect beak readings first
        try:
            competition_service.assert_front_of_queue(battery_id)
            return ScanResult(
                action_taken="needs_beak_readings",
                battery_id=battery_id,
            )
        except WrongBatteryError as exc:
            return ScanResult(
                action_taken="wrong_battery",
                battery_id=battery_id,
                error=exc,
            )

    # Cooling or Charging batteries should not be scanned — return informational result
    return ScanResult(
        action_taken=f"ignored_status_{status.lower()}",
        battery_id=battery_id,
    )
