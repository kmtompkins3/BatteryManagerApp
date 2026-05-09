"""CompetitionView — live competition queue with countdown timers and action buttons."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFrame,
)

from ui import theme
from app.services.competition_service import get_ordered_queue, QueueEntryDTO
from app.services.timer_service import check_cooling_timers, check_missing_candidates
from app.constants import BatteryStatus
import db.settings_dal as settings_dal


# Column index constants
COL_POS    = 0
COL_ID     = 1
COL_BRAND  = 2
COL_STATUS = 3
COL_TIMER  = 4
COL_ACTION = 5
COLUMN_HEADERS = ["Pos", "ID", "Brand", "Status", "Timer", "Action"]

# Status values that show the "SET TO CHARGING" button
READY_TO_CHARGE_STATUSES = {BatteryStatus.COOLING.value}

# Timer tick interval in milliseconds
TICK_INTERVAL_MS = 1000


class CompetitionView(QWidget):
    """
    Live competition queue view: shows ordered batteries with timers,
    status colors, action buttons, and 1-second timer ticks.
    """

    end_competition_requested        = pyqtSignal()
    set_charging_requested           = pyqtSignal(int)   # battery_id
    cooling_complete                 = pyqtSignal(int)   # battery_id
    battery_missing                  = pyqtSignal(int)   # battery_id
    add_battery_to_queue_requested   = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        # In-memory timer state: {battery_id: seconds_remaining (Cooling) or seconds_elapsed (OnField)}
        self._timer_state: dict[int, float] = {}

        # Track which status each battery had when we last built timer state
        self._battery_status: dict[int, str] = {}

        # Tracks batteries already emitted as missing this refresh cycle
        self._emitted_missing: set[int] = set()

        # Tracks batteries already emitted as cooling_complete this refresh cycle
        self._emitted_cooling_done: set[int] = set()

        # Last loaded queue entries (used for brand/pos lookup without a fresh DB hit)
        self._queue: list[QueueEntryDTO] = []

        self._build_ui()

        # 1-second tick timer
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(TICK_INTERVAL_MS)
        self._tick_timer.timeout.connect(self._tick)

    # -------------------------------------------------------------------------
    # UI construction
    # -------------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Assemble header banner and queue table into the root layout."""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_header())
        root_layout.addWidget(self._build_table(), stretch=1)

    def _build_header(self) -> QWidget:
        """Return the competition header banner with live badge, counts, and end button."""
        header = QFrame()
        header.setFixedHeight(72)
        header.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 rgba(255,66,0,0.12), stop:1 rgba(255,66,0,0.04)); "
            f"border-bottom: 1px solid {theme.BORDER};"
        )

        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        # "LIVE" badge
        live_badge = QLabel("  LIVE  ")
        live_badge.setFont(theme.get_font(bold=True, size=9))
        live_badge.setStyleSheet(
            f"background-color: {theme.ORANGE}; color: #ffffff; "
            f"padding: 3px 6px; border: none;"
        )
        live_badge.setFixedHeight(22)

        # Queue title
        queue_title = QLabel("Queue")
        queue_title.setFont(theme.get_font(bold=True, size=16))
        queue_title.setStyleSheet(f"color: {theme.TEXT};")

        # Status counts label — updated by refresh()
        self._counts_label = QLabel("0 ACTIVE · 0 MISSING")
        self._counts_label.setFont(theme.get_font(size=10))
        self._counts_label.setStyleSheet(f"color: {theme.TEXT_DIM};")

        # Add battery to queue button
        add_btn = theme.make_primary_button("+ ADD BATTERY")
        add_btn.setFixedHeight(34)
        add_btn.clicked.connect(self.add_battery_to_queue_requested.emit)

        # End competition button
        end_btn = theme.make_danger_button("END COMPETITION")
        end_btn.setFixedHeight(34)
        end_btn.clicked.connect(self.end_competition_requested.emit)

        layout.addWidget(live_badge)
        layout.addWidget(queue_title)
        layout.addWidget(self._counts_label)
        layout.addStretch()
        layout.addWidget(add_btn)
        layout.addWidget(end_btn)

        return header

    def _build_table(self) -> QTableWidget:
        """Return the configured QTableWidget for the competition queue."""
        self._table = QTableWidget()
        self._table.setColumnCount(len(COLUMN_HEADERS))
        self._table.setHorizontalHeaderLabels(COLUMN_HEADERS)
        self._table.setFont(theme.get_font(size=11))
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(False)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(COL_POS,    QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_ID,     QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_BRAND,  QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_STATUS, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(COL_TIMER,  QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_ACTION, QHeaderView.ResizeMode.ResizeToContents)
        # STATUS COLUMN WIDTH — change the value below to resize the Status column
        header.resizeSection(COL_STATUS, 140)

        return self._table

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def refresh(self) -> None:
        """Reload the queue from DB, rebuild the table, and reset timer state."""
        try:
            self._queue = get_ordered_queue()
        except Exception:
            # Competition may not be active yet; stay with last known queue
            self._queue = []

        # Reset signal emission guards when a full refresh occurs
        self._emitted_missing      = set()
        self._emitted_cooling_done = set()

        self._build_timer_state(self._queue)
        self._rebuild_table()
        self._update_counts_label()

    def start_ticking(self) -> None:
        """Start the 1-second interval timer."""
        self._tick_timer.start()

    def stop_ticking(self) -> None:
        """Stop the 1-second interval timer."""
        self._tick_timer.stop()

    # -------------------------------------------------------------------------
    # Timer logic
    # -------------------------------------------------------------------------

    def _build_timer_state(self, queue_entries: list[QueueEntryDTO]) -> None:
        """
        Build the in-memory timer dict from DB timestamps.
        Cooling batteries get remaining_seconds; OnField batteries get elapsed_seconds.
        """
        self._timer_state   = {}
        self._battery_status = {}
        now = datetime.now()

        cooling_minutes = settings_dal.get_setting_int("cooling_minutes", 15)
        cooling_seconds_total = cooling_minutes * 60

        for entry in queue_entries:
            self._battery_status[entry.battery_id] = entry.status

            if entry.status == BatteryStatus.COOLING.value:
                if entry.cooling_start_time is not None:
                    elapsed = (now - entry.cooling_start_time).total_seconds()
                    remaining = max(0.0, cooling_seconds_total - elapsed)
                    self._timer_state[entry.battery_id] = remaining
                else:
                    self._timer_state[entry.battery_id] = float(cooling_seconds_total)

            elif entry.status == BatteryStatus.ON_FIELD.value:
                if entry.scan_out_time is not None:
                    elapsed = (now - entry.scan_out_time).total_seconds()
                    self._timer_state[entry.battery_id] = elapsed
                else:
                    self._timer_state[entry.battery_id] = 0.0

    def _tick(self) -> None:
        """
        Called every second: decrement Cooling timers, increment OnField timers,
        fire signals when thresholds are crossed, then refresh the timer column.
        """
        missing_threshold_seconds = settings_dal.get_setting_int("comp_missing_minutes", 30) * 60

        for battery_id, status in list(self._battery_status.items()):
            if status == BatteryStatus.COOLING.value:
                current = self._timer_state.get(battery_id, 0.0)
                new_val = max(0.0, current - 1.0)
                self._timer_state[battery_id] = new_val

                # Emit cooling_complete once when the timer reaches zero
                if new_val <= 0.0 and battery_id not in self._emitted_cooling_done:
                    self._emitted_cooling_done.add(battery_id)
                    # Mark locally as ready so the UI updates immediately
                    self._battery_status[battery_id] = "ReadyToCharge"
                    self.cooling_complete.emit(battery_id)

            elif status == BatteryStatus.ON_FIELD.value:
                current = self._timer_state.get(battery_id, 0.0)
                new_val = current + 1.0
                self._timer_state[battery_id] = new_val

                # Emit battery_missing once when on-field time exceeds threshold
                if new_val >= missing_threshold_seconds and battery_id not in self._emitted_missing:
                    self._emitted_missing.add(battery_id)
                    self.battery_missing.emit(battery_id)

        self._refresh_timer_column()

    def _refresh_timer_column(self) -> None:
        """Update only the timer column cells without rebuilding the full table."""
        for row_index in range(self._table.rowCount()):
            id_item = self._table.item(row_index, COL_ID)
            if id_item is None:
                continue

            battery_id = int(id_item.text())
            status = self._battery_status.get(battery_id, "")
            timer_text = self._format_timer(battery_id, status)

            timer_item = self._table.item(row_index, COL_TIMER)
            if timer_item is not None:
                timer_item.setText(timer_text)
            else:
                self._table.setItem(row_index, COL_TIMER, _read_only_item(timer_text))

            # Update action button when status transitions to ReadyToCharge
            if status == "ReadyToCharge":
                existing_widget = self._table.cellWidget(row_index, COL_ACTION)
                if existing_widget is None:
                    self._table.setCellWidget(
                        row_index, COL_ACTION,
                        _make_charge_button(battery_id, self.set_charging_requested.emit),
                    )

    # -------------------------------------------------------------------------
    # Table construction
    # -------------------------------------------------------------------------

    def _rebuild_table(self) -> None:
        """Rebuild all rows in the queue table from self._queue."""
        self._table.setRowCount(0)

        for display_pos, entry in enumerate(self._queue, start=1):
            row_index = self._table.rowCount()
            self._table.insertRow(row_index)

            battery_id = entry.battery_id
            status     = self._battery_status.get(battery_id, entry.status)
            is_missing = entry.status == BatteryStatus.MISSING.value
            is_front   = display_pos == 1 and not is_missing

            # Background row tint
            if is_missing:
                row_bg = "rgba(220,0,0,0.06)"
            elif is_front:
                row_bg = "rgba(255,66,0,0.06)"
            else:
                row_bg = "transparent"

            # Position cell with colored left border
            pos_label = _make_position_label(str(display_pos), is_front, is_missing)
            self._table.setCellWidget(row_index, COL_POS, pos_label)

            # Plain text cells
            brand = self._brand_for(battery_id)
            self._table.setItem(row_index, COL_ID,    _read_only_item(str(battery_id), row_bg))
            self._table.setItem(row_index, COL_BRAND, _read_only_item(brand, row_bg))

            # Timer
            timer_text = self._format_timer(battery_id, status)
            self._table.setItem(row_index, COL_TIMER, _read_only_item(timer_text, row_bg))

            # Status dot
            status_widget = _make_status_dot_widget(entry.status)
            self._table.setCellWidget(row_index, COL_STATUS, status_widget)

            # Action button: show for Cooling / ReadyToCharge batteries
            if status in (BatteryStatus.COOLING.value, "ReadyToCharge"):
                charge_btn = _make_charge_button(battery_id, self.set_charging_requested.emit)
                self._table.setCellWidget(row_index, COL_ACTION, charge_btn)

        self._table.resizeRowsToContents()

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _format_timer(self, battery_id: int, status: str) -> str:
        """Return a formatted timer string for a battery, or blank if not applicable."""
        seconds = self._timer_state.get(battery_id)
        if seconds is None:
            return ""
        if status == BatteryStatus.COOLING.value:
            return _format_duration(seconds)
        if status == BatteryStatus.ON_FIELD.value:
            return _format_duration(seconds)
        if status == "ReadyToCharge":
            return "0m 0s"
        return ""

    def _brand_for(self, battery_id: int) -> str:
        """Return the brand string for a battery from the cached queue list."""
        # The queue DTO doesn't carry brand; we return a placeholder.
        # The main window can enrich this by connecting to battery_service if needed.
        return f"#{battery_id}"

    def _update_counts_label(self) -> None:
        """Recompute active/missing counts and update the header label."""
        active_count  = sum(1 for e in self._queue if e.status != BatteryStatus.MISSING.value)
        missing_count = sum(1 for e in self._queue if e.status == BatteryStatus.MISSING.value)
        self._counts_label.setText(f"{active_count} ACTIVE · {missing_count} MISSING")


# -------------------------------------------------------------------------
# Module-level helper functions
# -------------------------------------------------------------------------

def _read_only_item(text: str, background: str = "transparent") -> QTableWidgetItem:
    """Return a non-editable QTableWidgetItem, optionally with a tinted background."""
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    if background and background != "transparent":
        item.setBackground(QTableWidgetItem().background())  # let stylesheet handle it
    return item


def _make_status_dot_widget(status_value: str) -> QLabel:
    """Return a QLabel with a colored dot and label for use in a table cell."""
    color = theme.status_color(status_value)
    label = QLabel(f"● {status_value}")
    label.setFont(theme.get_font(size=11))
    label.setStyleSheet(
        f"color: {color}; background-color: transparent; padding: 4px 12px;"
    )
    label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    return label


def _make_position_label(pos_text: str, is_front: bool, is_missing: bool) -> QLabel:
    """
    Return a QLabel for the position column.
    Front-of-queue gets an orange left border; missing gets red; others get gray.
    """
    if is_missing:
        border_color = theme.RED
    elif is_front:
        border_color = theme.ORANGE
    else:
        border_color = theme.GRAY

    label = QLabel(pos_text)
    label.setFont(theme.get_font(bold=True, size=11))
    label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
    label.setStyleSheet(
        f"color: {theme.TEXT}; "
        f"border-left: 3px solid {border_color}; "
        f"background-color: transparent; "
        f"padding: 4px 12px;"
    )
    return label


def _make_charge_button(battery_id: int, emit_fn) -> QPushButton:
    """Return a small 'SET TO CHARGING' button wired to emit_fn(battery_id)."""
    btn = QPushButton("SET TO CHARGING")
    btn.setFont(theme.get_font(bold=True, size=9))
    btn.setFixedHeight(28)
    btn.setStyleSheet(f"""
        QPushButton {{
            background: transparent;
            color: {theme.PURPLE};
            border: 1px solid {theme.PURPLE};
            padding: 4px 10px;
        }}
        QPushButton:hover {{
            background: rgba(70,0,170,0.15);
        }}
    """)
    btn.clicked.connect(lambda: emit_fn(battery_id))
    return btn


def _format_duration(total_seconds: float) -> str:
    """Format a duration in seconds as 'Xm Ys'."""
    total_seconds = max(0.0, total_seconds)
    minutes = int(total_seconds) // 60
    seconds = int(total_seconds) % 60
    return f"{minutes}m {seconds}s"
