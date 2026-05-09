"""HomeView — Practice-mode battery fleet overview with embedded trend charts."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSizePolicy,
    QFrame,
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from ui import theme
from app.services.battery_service import list_active_batteries, BatteryDTO
from app.services.alert_service import compute_alerts_all_batteries_practice, AlertFlags
from db.session_dal import get_sessions_for_battery, get_total_uses
from db.beak_dal import get_readings_for_battery


# Column index constants — avoids magic numbers throughout the file
COL_ID         = 0
COL_STATUS     = 1
COL_VOLTAGE    = 2
COL_RESISTANCE = 3
COL_USES       = 4
COL_LAST_USED  = 5
COL_ALERTS     = 6
COLUMN_HEADERS = ["ID", "Status", "Latest Voltage", "Latest Resistance", "Uses", "Last Used", "Alerts"]

# How many beak readings to show in the trend chart
MAX_CHART_READINGS = 20


class _ChartPanel(QWidget):
    """Matplotlib canvas showing resistance and voltage trends for one battery."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(200)  # CHART PANEL HEIGHT — change this value to resize the top chart area
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Info label: shows battery ID, brand, batch, uses
        self._info_label = QLabel("No battery selected")
        self._info_label.setFont(theme.get_font(size=10))
        self._info_label.setStyleSheet(f"color: {theme.TEXT_DIM};")

        # Matplotlib figure with two side-by-side axes
        self._figure = Figure(figsize=(6, 1.4), facecolor=theme.BG)
        self._figure.subplots_adjust(left=0.08, right=0.95, top=0.82, bottom=0.2, wspace=0.4)
        self._ax_resistance, self._ax_voltage = self._figure.subplots(1, 2)
        self._style_axis(self._ax_resistance, "Resistance (mΩ)")
        self._style_axis(self._ax_voltage, "Voltage (V)")

        self._canvas = FigureCanvas(self._figure)
        self._canvas.setStyleSheet(f"background-color: {theme.BG};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._info_label)
        layout.addWidget(self._canvas)

    def _style_axis(self, ax, ylabel: str) -> None:
        """Apply dark theme styling to a matplotlib axis."""
        ax.set_facecolor(theme.BG)
        ax.tick_params(colors=theme.TEXT_DIM, labelsize=7)
        ax.set_ylabel(ylabel, color=theme.TEXT_DIM, fontsize=7)
        ax.set_xlabel("Reading #", color=theme.TEXT_DIM, fontsize=7)
        for spine in ax.spines.values():
            spine.set_edgecolor(theme.BORDER)

    def update_battery_info(self, label_text: str) -> None:
        """Update the descriptive label above the charts."""
        self._info_label.setText(label_text)

    def plot(self, readings) -> None:
        """Redraw both axes with the last MAX_CHART_READINGS beak readings."""
        recent = readings[-MAX_CHART_READINGS:]

        self._ax_resistance.cla()
        self._ax_voltage.cla()
        self._style_axis(self._ax_resistance, "Resistance (mΩ)")
        self._style_axis(self._ax_voltage, "Voltage (V)")

        if not recent:
            self._ax_resistance.text(
                0.5, 0.5, "No data",
                transform=self._ax_resistance.transAxes,
                color=theme.TEXT_DIM, ha="center", va="center", fontsize=9,
            )
            self._ax_voltage.text(
                0.5, 0.5, "No data",
                transform=self._ax_voltage.transAxes,
                color=theme.TEXT_DIM, ha="center", va="center", fontsize=9,
            )
        else:
            x_values = list(range(1, len(recent) + 1))
            resistance_values = [r.resistance_mohm for r in recent]
            voltage_values    = [r.voltage          for r in recent]

            self._ax_resistance.plot(
                x_values, resistance_values,
                color=theme.BLUE, linewidth=1.5, marker="o", markersize=3,
            )
            self._ax_voltage.plot(
                x_values, voltage_values,
                color=theme.ORANGE, linewidth=1.5, marker="o", markersize=3,
            )
            self._ax_resistance.set_xticks(x_values)
            self._ax_voltage.set_xticks(x_values)

        self._canvas.draw()

    def clear(self) -> None:
        """Reset charts to empty state."""
        self.plot([])
        self._info_label.setText("No battery selected")


class HomeView(QWidget):
    """
    Practice-mode fleet overview: trend charts for the selected battery,
    a toolbar with a NEW BATTERY button, and a scrollable battery table.
    """

    add_battery_requested   = pyqtSignal()
    battery_selected        = pyqtSignal(int)   # battery_id
    edit_battery_requested  = pyqtSignal(int)   # battery_id
    retire_battery_requested = pyqtSignal(int)  # battery_id

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._selected_battery_id: Optional[int] = None
        self._batteries: list[BatteryDTO] = []
        self._alerts_map: dict[int, AlertFlags] = {}
        self._show_retired: bool = False
        self._build_ui()

    # -------------------------------------------------------------------------
    # UI construction
    # -------------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Assemble all child widgets into the main vertical layout."""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_chart_panel())
        root_layout.addWidget(self._build_toolbar())
        root_layout.addWidget(self._build_table(), stretch=1)

    def _build_chart_panel(self) -> QWidget:
        """Return the chart panel widget."""
        self._chart_panel = _ChartPanel()
        wrapper = QFrame()
        wrapper.setStyleSheet(f"background-color: {theme.BG2}; border-bottom: 1px solid {theme.BORDER};")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.addWidget(self._chart_panel)
        return wrapper

    def _build_toolbar(self) -> QWidget:
        """Return the toolbar row with fleet title and NEW BATTERY button."""
        toolbar = QWidget()
        toolbar.setFixedHeight(52)
        toolbar.setStyleSheet(f"background-color: {theme.BG}; border-bottom: 1px solid {theme.BORDER};")

        h_layout = QHBoxLayout(toolbar)
        h_layout.setContentsMargins(16, 0, 16, 0)

        title_label = QLabel("Active Fleet")
        title_label.setFont(theme.get_font(bold=True, size=14))
        title_label.setStyleSheet(f"color: {theme.TEXT};")

        new_battery_btn = theme.make_primary_button("+ NEW BATTERY")
        new_battery_btn.setFixedHeight(34)
        new_battery_btn.clicked.connect(self.add_battery_requested.emit)

        self._show_retired_btn = theme.make_ghost_button("Show Retired")
        self._show_retired_btn.setFixedHeight(34)
        self._show_retired_btn.setCheckable(True)
        self._show_retired_btn.toggled.connect(self._on_show_retired_toggled)

        h_layout.addWidget(title_label)
        h_layout.addStretch()
        h_layout.addWidget(new_battery_btn)
        h_layout.addWidget(self._show_retired_btn)

        return toolbar

    def _build_table(self) -> QTableWidget:
        """Return the configured QTableWidget for the battery fleet."""
        self._table = QTableWidget()
        self._table.setColumnCount(len(COLUMN_HEADERS))
        self._table.setHorizontalHeaderLabels(COLUMN_HEADERS)
        self._table.setFont(theme.get_font(size=11))
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(False)

        # Column widths
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(COL_ID,         QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_STATUS,     QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(COL_VOLTAGE,    QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_RESISTANCE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_USES,       QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_LAST_USED,  QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_ALERTS,     QHeaderView.ResizeMode.ResizeToContents)
        # STATUS COLUMN WIDTH — change the value below to resize the Status column
        header.resizeSection(COL_STATUS, 140)

        self._table.cellClicked.connect(self._on_row_clicked)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_table_context_menu)
        return self._table

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def refresh(self) -> None:
        """Reload batteries from DB, repopulate table, refresh charts."""
        from app.services.battery_service import list_all_batteries
        self._batteries  = list_all_batteries() if self._show_retired else list_active_batteries()
        self._alerts_map = compute_alerts_all_batteries_practice()
        self._populate_table(self._batteries, self._alerts_map)

        # Restore chart for previously selected battery if it still exists
        if self._selected_battery_id is not None:
            still_exists = any(b.battery_id == self._selected_battery_id for b in self._batteries)
            if still_exists:
                self._update_charts(self._selected_battery_id)
            else:
                self._selected_battery_id = None
                self._chart_panel.clear()

    # -------------------------------------------------------------------------
    # Slot handlers
    # -------------------------------------------------------------------------

    def _on_row_clicked(self, row: int, col: int) -> None:
        """Emit battery_selected and trigger chart update when a row is clicked."""
        id_item = self._table.item(row, COL_ID)
        if id_item is None:
            return
        battery_id = int(id_item.text())
        self._selected_battery_id = battery_id
        self.battery_selected.emit(battery_id)
        self._update_charts(battery_id)

    def _on_table_context_menu(self, pos) -> None:
        """Show Edit/Retire context menu when the user right-clicks a battery row."""
        from PyQt6.QtWidgets import QMenu
        index = self._table.indexAt(pos)
        if not index.isValid():
            return
        row = index.row()
        id_item = self._table.item(row, COL_ID)
        if id_item is None:
            return
        battery_id = int(id_item.text())

        # Look up battery in cached list to check retired status
        battery = next((b for b in self._batteries if b.battery_id == battery_id), None)

        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background: {theme.BG2}; color: {theme.TEXT}; border: 1px solid {theme.BORDER}; }}"
            f"QMenu::item:selected {{ background: {theme.BG3}; }}"
        )
        edit_action   = menu.addAction("✎  Edit Battery")
        retire_action = menu.addAction("⊗  Retire Battery")

        # Disable retire option if the battery is already retired
        if battery and battery.retired:
            retire_action.setEnabled(False)

        chosen = menu.exec(self._table.viewport().mapToGlobal(pos))
        if chosen == edit_action:
            self.edit_battery_requested.emit(battery_id)
        elif chosen == retire_action:
            self.retire_battery_requested.emit(battery_id)

    def _on_show_retired_toggled(self, checked: bool) -> None:
        """Update show_retired flag and reload the battery table."""
        self._show_retired = checked
        self.refresh()

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _populate_table(self, batteries: list[BatteryDTO], alerts_map: dict[int, AlertFlags]) -> None:
        """Fill all QTableWidget rows from the given battery list."""
        self._table.setRowCount(0)

        for battery in batteries:
            row_index = self._table.rowCount()
            self._table.insertRow(row_index)

            battery_id = battery.battery_id
            total_uses = get_total_uses(battery_id)
            readings   = get_readings_for_battery(battery_id)
            flags      = alerts_map.get(battery_id, AlertFlags())

            # Derive display values from beak readings
            latest_voltage    = f"{readings[-1].voltage:.2f} V"    if readings else "—"
            latest_resistance = f"{readings[-1].resistance_mohm:.1f} mΩ" if readings else "—"

            # Last used: most recent closed session
            sessions = get_sessions_for_battery(battery_id)
            closed   = [s for s in sessions if s.scan_in_time is not None]
            last_used_text = (
                max(s.scan_in_time for s in closed).strftime("%Y-%m-%d") if closed else "Never"
            )

            # Current status: inferred from whether an open session exists
            open_session = next((s for s in sessions if s.scan_in_time is None), None)
            status_value = "OnField" if open_session else "Available"

            # Alert indicator
            alert_messages = []
            if flags.not_scanned_in:
                alert_messages.append("Not scanned in recently")
            if flags.not_used:
                alert_messages.append("Not used recently")
            if flags.not_tested:
                alert_messages.append("Capacity test overdue")
            if flags.usage_imbalance:
                alert_messages.append("Usage imbalance across fleet")
            has_alert = bool(alert_messages)
            alert_tooltip = "\n".join(alert_messages) if alert_messages else ""

            # Populate plain-text cells
            self._table.setItem(row_index, COL_ID,         _read_only_item(str(battery_id)))
            self._table.setItem(row_index, COL_VOLTAGE,    _read_only_item(latest_voltage))
            self._table.setItem(row_index, COL_RESISTANCE, _read_only_item(latest_resistance))
            self._table.setItem(row_index, COL_USES,       _read_only_item(str(total_uses)))
            self._table.setItem(row_index, COL_LAST_USED,  _read_only_item(last_used_text))
            alert_item = _read_only_item("⚠" if has_alert else "")
            if alert_tooltip:
                alert_item.setToolTip(alert_tooltip)
            self._table.setItem(row_index, COL_ALERTS, alert_item)

            # Status dot widget
            status_widget = _make_status_dot_widget(status_value)
            self._table.setCellWidget(row_index, COL_STATUS, status_widget)

            # Grey out retired battery rows and show a "Retired" status dot
            if battery.retired:
                for col in range(self._table.columnCount()):
                    item = self._table.item(row_index, col)
                    if item:
                        item.setForeground(QColor(theme.TEXT_FAINT))
                retired_widget = _make_status_dot_widget("Retired")
                self._table.setCellWidget(row_index, COL_STATUS, retired_widget)

        self._table.resizeRowsToContents()

    def _update_charts(self, battery_id: int) -> None:
        """Query beak readings for battery_id and redraw the chart panel."""
        battery = next((b for b in self._batteries if b.battery_id == battery_id), None)
        if battery is None:
            self._chart_panel.clear()
            return

        total_uses = get_total_uses(battery_id)
        info_text = (
            f"Battery #{battery_id}  ·  {battery.brand}  ·  Batch: {battery.batch_number}  ·  Uses: {total_uses}"
        )
        self._chart_panel.update_battery_info(info_text)

        readings = get_readings_for_battery(battery_id)
        self._chart_panel.plot(readings)


# -------------------------------------------------------------------------
# Module-level helper functions
# -------------------------------------------------------------------------

def _read_only_item(text: str) -> QTableWidgetItem:
    """Return a non-editable, vertically centered QTableWidgetItem."""
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    return item


def _make_status_dot_widget(status_value: str) -> QLabel:
    """Return a QLabel showing a colored dot and status name for use in a table cell."""
    color = theme.status_color(status_value)
    label = QLabel(f"● {status_value}")
    label.setFont(theme.get_font(size=11))
    label.setStyleSheet(
        f"color: {color}; background-color: transparent; padding: 4px 12px;"
    )
    label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    return label
