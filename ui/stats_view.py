"""StatsView — per-battery statistics, history table, graphs, and capacity entry."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QScrollArea, QLineEdit, QSizePolicy, QGridLayout,
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from ui import theme
from app.services.battery_service import get_battery, BatteryDTO
from app.services.capacity_service import record_capacity_test, get_capacity_tests, CapacityTestDTO
from app.services.export_service import export_battery_history_csv, generate_qr_pdf
from db.session_dal import get_sessions_for_battery
from db.beak_dal import get_readings_for_battery

# Session history table column indexes
HIST_COL_DATETIME   = 0
HIST_COL_DURATION   = 1
HIST_COL_VOLTAGE    = 2
HIST_COL_CHARGE     = 3
HIST_COL_RESISTANCE = 4
HIST_HEADERS = ["Date / Time", "Duration (min)", "Voltage (V)", "Charge (%)", "Resistance (mΩ)"]


class StatsView(QWidget):
    """
    Per-battery statistics page. Call load_battery(battery_id) to populate.
    Shows battery properties, aggregate stats, three embedded charts, a
    capacity test entry form, and a full session history table.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._battery_id: Optional[int] = None
        self._build_ui()

    # -------------------------------------------------------------------------
    # UI construction
    # -------------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Wrap all content in a QScrollArea so the page scrolls vertically."""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {theme.BG}; }}")

        # Inner container holds everything
        inner = QWidget()
        inner.setStyleSheet(f"background: {theme.BG};")
        self._inner_layout = QVBoxLayout(inner)
        self._inner_layout.setContentsMargins(32, 24, 32, 32)
        self._inner_layout.setSpacing(24)

        self._inner_layout.addWidget(self._build_header())
        self._inner_layout.addWidget(self._build_properties_section())
        self._inner_layout.addWidget(self._build_charts_section())
        self._inner_layout.addWidget(self._build_capacity_section())
        self._inner_layout.addWidget(self._build_history_section())

        scroll.setWidget(inner)
        outer.addWidget(scroll)

    def _build_header(self) -> QWidget:
        """Return the header row: battery ID title + brand info + Print QR button."""
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)

        self._title_label = QLabel("Select a battery")
        self._title_label.setFont(theme.get_font(bold=True, size=20))
        self._title_label.setStyleSheet(f"color: {theme.TEXT};")

        self._subtitle_label = QLabel("")
        self._subtitle_label.setFont(theme.get_font(size=11))
        self._subtitle_label.setStyleSheet(f"color: {theme.TEXT_DIM};")

        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        text_col.addWidget(self._title_label)
        text_col.addWidget(self._subtitle_label)

        self._print_qr_btn = theme.make_ghost_button("PRINT QR LABEL")
        self._print_qr_btn.setEnabled(False)
        self._print_qr_btn.clicked.connect(self._on_print_qr)

        layout.addLayout(text_col)
        layout.addStretch()
        layout.addWidget(self._print_qr_btn)
        return wrapper

    def _build_properties_section(self) -> QWidget:
        """Return a two-column grid of battery properties and aggregate stats."""
        section = _section_widget("BATTERY PROPERTIES")
        self._props_grid = QGridLayout()
        self._props_grid.setHorizontalSpacing(24)
        self._props_grid.setVerticalSpacing(10)
        section.layout().addLayout(self._props_grid)
        return section

    def _build_charts_section(self) -> QWidget:
        """Return three stacked matplotlib charts: voltage/uses, resistance/uses, capacity."""
        section = _section_widget("CHARTS")
        layout = section.layout()

        # Chart 1: Voltage over uses
        self._fig_voltage_uses = Figure(figsize=(8, 2.2), facecolor=theme.BG)
        self._canvas_voltage_uses = FigureCanvas(self._fig_voltage_uses)
        self._canvas_voltage_uses.setStyleSheet(f"background: {theme.BG};")
        self._canvas_voltage_uses.setMinimumHeight(180)

        # Chart 2: Resistance over uses
        self._fig_resistance_uses = Figure(figsize=(8, 2.2), facecolor=theme.BG)
        self._canvas_resistance_uses = FigureCanvas(self._fig_resistance_uses)
        self._canvas_resistance_uses.setStyleSheet(f"background: {theme.BG};")
        self._canvas_resistance_uses.setMinimumHeight(180)

        # Chart 3: Tracking capacity readings
        self._fig_capacity = Figure(figsize=(8, 2.0), facecolor=theme.BG)
        self._canvas_capacity = FigureCanvas(self._fig_capacity)
        self._canvas_capacity.setStyleSheet(f"background: {theme.BG};")
        self._canvas_capacity.setMinimumHeight(160)

        for canvas in (self._canvas_voltage_uses, self._canvas_resistance_uses, self._canvas_capacity):
            sep = _thin_separator()
            layout.addWidget(canvas)
            layout.addWidget(sep)

        return section

    def _build_capacity_section(self) -> QWidget:
        """Return the capacity test entry widget."""
        section = _section_widget("RECORD CAPACITY TEST")
        layout = section.layout()

        instruction = QLabel("Enter the measured capacity in amp-hours (e.g. 12.5).")
        instruction.setFont(theme.get_font(size=10))
        instruction.setStyleSheet(f"color: {theme.TEXT_DIM};")
        layout.addWidget(instruction)

        entry_row = QHBoxLayout()
        self._capacity_edit = QLineEdit()
        self._capacity_edit.setPlaceholderText("Ah value, e.g. 12.5")
        self._capacity_edit.setFont(theme.get_font(size=12))
        self._capacity_edit.setFixedWidth(200)
        ah_label = QLabel("Ah")
        ah_label.setFont(theme.get_font(size=11))
        ah_label.setStyleSheet(f"color: {theme.TEXT_DIM};")

        self._record_test_btn = theme.make_primary_button("RECORD TEST")
        self._record_test_btn.setEnabled(False)
        self._record_test_btn.clicked.connect(self._on_record_capacity_test)

        self._capacity_error = QLabel("")
        self._capacity_error.setFont(theme.get_font(size=9))
        self._capacity_error.setStyleSheet(f"color: {theme.RED};")

        entry_row.addWidget(self._capacity_edit)
        entry_row.addWidget(ah_label)
        entry_row.addWidget(self._record_test_btn)
        entry_row.addWidget(self._capacity_error)
        entry_row.addStretch()
        layout.addLayout(entry_row)

        self._capacity_edit.textChanged.connect(self._on_capacity_text_changed)
        return section

    def _build_history_section(self) -> QWidget:
        """Return the session history section with table and CSV export button."""
        section = _section_widget("SESSION HISTORY")
        layout = section.layout()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._export_btn = theme.make_ghost_button("EXPORT CSV")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._on_export_csv)
        btn_row.addWidget(self._export_btn)
        layout.addLayout(btn_row)

        self._history_table = QTableWidget()
        self._history_table.setColumnCount(len(HIST_HEADERS))
        self._history_table.setHorizontalHeaderLabels(HIST_HEADERS)
        self._history_table.setFont(theme.get_font(size=11))
        self._history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._history_table.verticalHeader().setVisible(False)
        self._history_table.setSortingEnabled(True)
        self._history_table.setMinimumHeight(200)

        header = self._history_table.horizontalHeader()
        header.setSectionResizeMode(HIST_COL_DATETIME, QHeaderView.ResizeMode.Stretch)
        for col in (HIST_COL_DURATION, HIST_COL_VOLTAGE, HIST_COL_CHARGE, HIST_COL_RESISTANCE):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self._history_table)
        return section

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def load_battery(self, battery_id: int) -> None:
        """Fetch all data for battery_id and populate every widget on this page."""
        self._battery_id = battery_id
        try:
            battery = get_battery(battery_id)
        except Exception:
            self._title_label.setText(f"Battery #{battery_id} not found")
            return

        sessions  = get_sessions_for_battery(battery_id)
        readings  = get_readings_for_battery(battery_id)
        cap_tests = get_capacity_tests(battery_id)

        # Map session_id → BeakReadingRow for fast lookup in history table
        reading_by_session = {r.session_id: r for r in readings}

        self._populate_header(battery)
        self._populate_properties(battery, sessions)
        self._draw_voltage_uses_chart(readings)
        self._draw_resistance_uses_chart(readings)
        self._draw_capacity_chart(cap_tests)
        self._populate_history_table(sessions, reading_by_session)

        self._print_qr_btn.setEnabled(True)
        self._record_test_btn.setEnabled(True)
        self._export_btn.setEnabled(True)

    # -------------------------------------------------------------------------
    # Data population helpers
    # -------------------------------------------------------------------------

    def _populate_header(self, battery: BatteryDTO) -> None:
        """Update the page title and subtitle from the battery DTO."""
        self._title_label.setText(f"Battery #{battery.battery_id}")
        self._subtitle_label.setText(
            f"{battery.brand}  ·  Batch: {battery.batch_number}"
            + ("  ·  RETIRED" if battery.retired else "")
        )

    def _populate_properties(self, battery: BatteryDTO, sessions) -> None:
        """Populate the properties grid with battery fields and aggregate stats."""
        # Clear previous rows
        while self._props_grid.count():
            item = self._props_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        closed = [s for s in sessions if s.scan_in_time is not None]
        total_uses = len(closed)
        total_hours = sum(
            s.duration_minutes for s in closed if s.duration_minutes is not None
        ) / 60.0

        rows = [
            ("Battery ID",     str(battery.battery_id)),
            ("Brand",          battery.brand),
            ("Batch Number",   battery.batch_number),
            ("Purchase Date",  str(battery.purchase_date) if battery.purchase_date else "—"),
            ("Date Added",     battery.date_added.strftime("%Y-%m-%d")),
            ("Broken In",      "Yes" if battery.broken_in else "No"),
            ("Total Uses",     str(total_uses)),
            ("Total Hours",    f"{total_hours:.1f} h"),
        ]

        for row_i, (label, value) in enumerate(rows):
            col = (row_i % 2) * 2
            row = row_i // 2
            lbl = QLabel(label)
            lbl.setFont(theme.get_font(size=9))
            lbl.setStyleSheet(f"color: {theme.TEXT_DIM};")
            val = QLabel(value)
            val.setFont(theme.get_font(bold=True, size=11))
            val.setStyleSheet(f"color: {theme.TEXT};")
            self._props_grid.addWidget(lbl, row * 2,     col)
            self._props_grid.addWidget(val, row * 2 + 1, col)

    def _populate_history_table(self, sessions, reading_by_session) -> None:
        """Fill the history table from sessions + readings, most recent first."""
        # Sort by scan_out_time descending
        sorted_sessions = sorted(
            sessions, key=lambda s: s.scan_out_time, reverse=True
        )
        self._history_table.setRowCount(0)

        for session in sorted_sessions:
            row = self._history_table.rowCount()
            self._history_table.insertRow(row)

            if session.override_used:
                for col, text in enumerate(["Override"] * len(HIST_HEADERS)):
                    self._history_table.setItem(row, col, _ro_item(text))
            else:
                reading = reading_by_session.get(session.session_id)
                dt_text  = session.scan_out_time.strftime("%Y-%m-%d %H:%M") if session.scan_out_time else "—"
                dur_text = f"{session.duration_minutes:.1f}" if session.duration_minutes is not None else "—"
                v_text   = f"{reading.voltage:.2f}"      if reading else "—"
                c_text   = str(reading.charge_pct)       if reading else "—"
                r_text   = f"{reading.resistance_mohm:.1f}" if reading else "—"
                for col, text in enumerate([dt_text, dur_text, v_text, c_text, r_text]):
                    self._history_table.setItem(row, col, _ro_item(text))

        self._history_table.resizeRowsToContents()

    # -------------------------------------------------------------------------
    # Chart drawing
    # -------------------------------------------------------------------------

    def _draw_voltage_uses_chart(self, readings) -> None:
        """Chart: voltage vs. use number."""
        self._fig_voltage_uses.clear()
        ax = self._fig_voltage_uses.add_subplot(111)
        _style_ax(ax, "Voltage over Uses")

        if not readings:
            ax.text(0.5, 0.5, "No data", transform=ax.transAxes,
                    color=theme.TEXT_DIM, ha="center", va="center", fontsize=10)
        else:
            use_nums = list(range(1, len(readings) + 1))
            voltages = [r.voltage for r in readings]
            ax.plot(use_nums, voltages, color=theme.ORANGE, label="Voltage (V)",
                    linewidth=1.5, marker="o", markersize=3)
            ax.set_xlabel("Use #", color=theme.TEXT_DIM, fontsize=8)
            ax.set_ylabel("V", color=theme.TEXT_DIM, fontsize=8)
            ax.legend(fontsize=8, labelcolor=theme.TEXT_DIM,
                      facecolor=theme.BG2, edgecolor=theme.BORDER)

        self._canvas_voltage_uses.draw()

    def _draw_capacity_chart(self, cap_tests: list[CapacityTestDTO]) -> None:
        """Chart: tracking capacity readings over time."""
        self._fig_capacity.clear()
        ax = self._fig_capacity.add_subplot(111)
        _style_ax(ax, "Tracking Capacity Readings (Ah)")

        if not cap_tests:
            ax.text(0.5, 0.5, "No capacity tests recorded",
                    transform=ax.transAxes, color=theme.TEXT_DIM,
                    ha="center", va="center", fontsize=10)
        else:
            sorted_tests = sorted(cap_tests, key=lambda t: t.test_date)
            dates   = [t.test_date for t in sorted_tests]
            values  = [t.capacity_ah for t in sorted_tests]
            ax.plot(dates, values, color=theme.PURPLE, linewidth=1.8,
                    marker="o", markersize=4, label="Capacity (Ah)")
            ax.set_ylabel("Ah", color=theme.TEXT_DIM, fontsize=8)
            self._fig_capacity.autofmt_xdate(rotation=30, ha="right")

        self._canvas_capacity.draw()

    def _draw_resistance_uses_chart(self, readings) -> None:
        """Chart: resistance vs. use number."""
        self._fig_resistance_uses.clear()
        ax = self._fig_resistance_uses.add_subplot(111)
        _style_ax(ax, "Resistance over Uses")

        if not readings:
            ax.text(0.5, 0.5, "No data", transform=ax.transAxes,
                    color=theme.TEXT_DIM, ha="center", va="center", fontsize=10)
        else:
            use_nums    = list(range(1, len(readings) + 1))
            resistances = [r.resistance_mohm for r in readings]
            ax.plot(use_nums, resistances, color=theme.BLUE, label="Resistance (mΩ)",
                    linewidth=1.5, marker="^", markersize=3)
            ax.set_xlabel("Use #", color=theme.TEXT_DIM, fontsize=8)
            ax.set_ylabel("mΩ", color=theme.TEXT_DIM, fontsize=8)
            ax.legend(fontsize=8, labelcolor=theme.TEXT_DIM,
                      facecolor=theme.BG2, edgecolor=theme.BORDER)

        self._canvas_resistance_uses.draw()

    # -------------------------------------------------------------------------
    # Button handlers
    # -------------------------------------------------------------------------

    def _on_capacity_text_changed(self, text: str) -> None:
        """Enable the Record Test button only when the field holds a valid float."""
        try:
            val = float(text.strip())
            self._record_test_btn.setEnabled(val > 0 and self._battery_id is not None)
            self._capacity_error.setText("")
        except ValueError:
            self._record_test_btn.setEnabled(False)

    def _on_record_capacity_test(self) -> None:
        """Save the entered capacity test and redraw the capacity chart."""
        if self._battery_id is None:
            return
        try:
            ah = float(self._capacity_edit.text().strip())
            record_capacity_test(self._battery_id, ah)
            self._capacity_edit.clear()
            self._capacity_error.setText("")
            # Refresh the capacity chart
            tests = get_capacity_tests(self._battery_id)
            self._draw_capacity_chart(tests)
        except (ValueError, Exception) as exc:
            self._capacity_error.setText(f"Error: {exc}")

    def _on_export_csv(self) -> None:
        """Export session history to CSV and open the exports folder."""
        if self._battery_id is None:
            return
        try:
            out_path = export_battery_history_csv(self._battery_id)
            os.startfile(str(out_path.parent))
        except Exception as exc:
            self._export_btn.setText(f"Error: {exc}")

    def _on_print_qr(self) -> None:
        """Generate the QR label PDF and open it in the default viewer."""
        if self._battery_id is None:
            return
        try:
            out_path = generate_qr_pdf(self._battery_id)
            os.startfile(str(out_path))
        except Exception as exc:
            self._print_qr_btn.setText(f"Error: {exc}")


# -------------------------------------------------------------------------
# Module-level helpers
# -------------------------------------------------------------------------

def _section_widget(title: str) -> QWidget:
    """Return a titled section container with a VBoxLayout for content."""
    wrapper = QWidget()
    wrapper.setStyleSheet(f"background: {theme.BG};")
    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)

    title_label = QLabel(title)
    title_label.setFont(theme.get_font(bold=True, size=10))
    title_label.setStyleSheet(
        f"color: {theme.TEXT_DIM}; "
        f"border-bottom: 1px solid {theme.BORDER}; "
        f"padding-bottom: 6px;"
    )
    layout.addWidget(title_label)
    return wrapper


def _thin_separator() -> QFrame:
    """Return a 1px horizontal rule in the border color."""
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setFixedHeight(1)
    sep.setStyleSheet(f"background: {theme.BORDER}; border: none;")
    return sep


def _style_ax(ax, title: str) -> None:
    """Apply the app dark theme to a matplotlib Axes instance."""
    ax.set_facecolor(theme.BG)
    ax.set_title(title, color=theme.TEXT_DIM, fontsize=9, pad=6)
    ax.tick_params(colors=theme.TEXT_DIM, labelsize=7)
    for spine in ax.spines.values():
        spine.set_edgecolor(theme.BORDER)
    ax.figure.patch.set_facecolor(theme.BG)


def _ro_item(text: str) -> QTableWidgetItem:
    """Return a non-editable, vertically centered QTableWidgetItem."""
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    return item
