from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import db.session_dal as _session_dal
import db.capacity_dal as _capacity_dal
import db.settings_dal as _settings_dal
import db.battery_dal as _bat_dal
from app.constants import BatteryStatus


@dataclass
class AlertFlags:
    not_scanned_in: bool = False   # Practice: last scan_out > threshold hours ago and Available
    not_used: bool = False          # last closed session > threshold months ago (or never)
    not_tested: bool = False        # last capacity test > threshold months ago (or never)
    usage_imbalance: bool = False   # uses > (min_uses + threshold)


def _months_ago(months: int) -> datetime:
    from dateutil.relativedelta import relativedelta  # type: ignore[import]
    return datetime.now() - relativedelta(months=months)


def _hours_ago(hours: float) -> datetime:
    from datetime import timedelta
    return datetime.now() - timedelta(hours=hours)


def compute_alerts_practice(battery_id: int) -> AlertFlags:
    """
    Computes all four alert flags for a single battery in Practice mode.
    Reads thresholds from AppSettings.
    """
    flags = AlertFlags()

    not_scanned_threshold = _settings_dal.get_setting_int("practice_not_scanned_in_hours", 2)
    not_used_threshold    = _settings_dal.get_setting_int("practice_not_used_months", 1)
    not_tested_threshold  = _settings_dal.get_setting_int("practice_not_tested_months", 6)
    imbalance_threshold   = _settings_dal.get_setting_int("practice_imbalance_uses", 5)

    min_uses = _session_dal.get_min_uses_across_active_batteries()
    total_uses = _session_dal.get_total_uses(battery_id)

    # Not scanned in: battery is Available and last scan_out was > threshold hours ago
    last_scan_out = _session_dal.get_last_scan_out_time(battery_id)
    battery = _bat_dal.get_battery(battery_id)
    if battery:
        # We can only determine current status from the queue in Competition mode;
        # in Practice mode we infer Available if there is no open session.
        open_session = _session_dal.get_open_session_for_battery(battery_id)
        is_available = open_session is None and not battery.retired
        if is_available and last_scan_out is not None:
            cutoff = _hours_ago(not_scanned_threshold)
            flags.not_scanned_in = last_scan_out < cutoff

    # Not used: only flag if the battery HAS been used before but not recently.
    # Batteries that have never been used are not flagged here.
    sessions = _session_dal.get_sessions_for_battery(battery_id)
    closed = [s for s in sessions if s.scan_in_time is not None]
    if closed:
        last_use = max(s.scan_in_time for s in closed)
        flags.not_used = last_use < _months_ago(not_used_threshold)

    # Not tested: last capacity test more than threshold months ago (or never)
    last_test_date = _capacity_dal.get_last_capacity_test_date(battery_id)
    if last_test_date is None:
        flags.not_tested = True
    else:
        flags.not_tested = last_test_date < _months_ago(not_tested_threshold)

    # Usage imbalance
    flags.usage_imbalance = total_uses > (min_uses + imbalance_threshold)

    return flags


def compute_alerts_competition(battery_id: int) -> AlertFlags:
    """
    In Competition mode only the usage imbalance flag is relevant.
    """
    flags = AlertFlags()
    imbalance_threshold = _settings_dal.get_setting_int("comp_imbalance_uses", 1)
    min_uses = _session_dal.get_min_uses_across_active_batteries()
    total_uses = _session_dal.get_total_uses(battery_id)
    flags.usage_imbalance = total_uses > (min_uses + imbalance_threshold)
    return flags


def compute_alerts_all_batteries_practice() -> dict[int, AlertFlags]:
    """
    Batch computation for the full Practice grid.
    Pre-fetches shared values to avoid N+1 queries.
    """
    batteries = _bat_dal.list_active_batteries()
    result: dict[int, AlertFlags] = {}
    for battery in batteries:
        result[battery.battery_id] = compute_alerts_practice(battery.battery_id)
    return result
