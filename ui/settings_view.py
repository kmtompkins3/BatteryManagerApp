"""SettingsView — Admin settings panel with threshold editing, PIN management, and override log."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFrame,
    QScrollArea,
    QSizePolicy,
    QMessageBox,
)

from ui import theme
import app.services.admin_service as admin_service
import db.override_dal as override_dal
from ui.dialogs import PinDialog, SetPinDialog


# ---------------------------------------------------------------------------
# Threshold metadata: display label, settings key, unit hint
# ---------------------------------------------------------------------------
THRESHOLD_FIELDS = [
    ("practice_not_scanned_in_hours",  "Practice — Not Scanned In (hours)",       "hours"),
    ("practice_not_used_months",       "Practice — Not Used (months)",             "months"),
    ("practice_not_tested_months",     "Practice — Not Tested (months)",           "months"),
    ("practice_imbalance_uses",        "Practice — Usage Imbalance (uses)",        "uses"),
    ("comp_missing_minutes",           "Competition — Missing Alert (minutes)",    "minutes"),
    ("comp_imbalance_uses",            "Competition — Usage Imbalance (uses)",     "uses"),
    ("cooling_minutes",                "Cooling Duration (minutes)",               "minutes"),
]

# Override log table columns
COL_TIMESTAMP   = 0
COL_BATTERY_ID  = 1
COL_ACTION      = 2
OVERRIDE_HEADERS = ["Timestamp", "Battery ID", "Action"]


class SettingsView(QWidget):
    """
    Admin settings panel with three sections:
    1. Threshold values — display only until unlocked via PIN
    2. PIN management — set or change the admin PIN
    3. Override log — read-only table of all override actions
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._is_unlocked = False

        # Maps settings key → QLineEdit widget for threshold fields
        self._threshold_inputs: dict[str, QLineEdit] = {}

        self._build_ui()

    # -------------------------------------------------------------------------
    # UI construction
    # -------------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build the full scrollable settings layout."""
        # Outer layout — holds scroll area
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {theme.BG}; border: none; }}"
            f"QScrollBar:vertical {{ background: {theme.BG2}; width: 8px; }}"
            f"QScrollBar::handle:vertical {{ background: {theme.BORDER2}; border-radius: 4px; }}"
        )

        content = QWidget()
        content.setStyleSheet(f"background-color: {theme.BG};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(24)

        content_layout.addWidget(self._build_page_header())
        content_layout.addWidget(self._build_thresholds_section())
        content_layout.addWidget(self._build_pin_section())
        content_layout.addWidget(self._build_override_log_section())
        content_layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _build_page_header(self) -> QWidget:
        """Title row with UNLOCK SETTINGS button."""
        header = QWidget()
        header.setStyleSheet(f"background-color: {theme.BG};")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Settings")
        title.setFont(theme.get_font(bold=True, size=18))
        title.setStyleSheet(f"color: {theme.TEXT};")

        self._unlock_btn = theme.make_ghost_button("🔒  UNLOCK SETTINGS")
        self._unlock_btn.setFixedHeight(36)
        self._unlock_btn.clicked.connect(self._on_unlock_clicked)

        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(self._unlock_btn)

        return header

    def _build_thresholds_section(self) -> QFrame:
        """Section card with all editable threshold fields."""
        card = self._make_card()
        layout = card.layout()

        # Section title row
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)

        section_title = QLabel("Alert Thresholds")
        section_title.setFont(theme.get_font(bold=True, size=13))
        section_title.setStyleSheet(f"color: {theme.TEXT};")

        self._save_btn = theme.make_primary_button("SAVE CHANGES")
        self._save_btn.setFixedHeight(32)
        self._save_btn.setVisible(False)
        self._save_btn.clicked.connect(self._on_save_thresholds)

        title_row.addWidget(section_title)
        title_row.addStretch()
        title_row.addWidget(self._save_btn)
        layout.addLayout(title_row)

        # Divider
        layout.addWidget(self._make_divider())

        # One row per threshold
        for key, label_text, unit in THRESHOLD_FIELDS:
            row = self._build_threshold_row(key, label_text, unit)
            layout.addWidget(row)

        return card

    def _build_threshold_row(self, key: str, label_text: str, unit: str) -> QWidget:
        """Single label + input row for a threshold field."""
        row = QWidget()
        row.setStyleSheet(f"background-color: transparent;")
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 6, 0, 6)
        h.setSpacing(16)

        label = QLabel(label_text)
        label.setFont(theme.get_font(size=11))
        label.setStyleSheet(f"color: {theme.TEXT_DIM};")
        label.setFixedWidth(340)

        field = QLineEdit()
        field.setFont(theme.get_font(size=11))
        field.setFixedWidth(100)
        field.setFixedHeight(30)
        field.setReadOnly(True)
        field.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        field.setStyleSheet(self._field_style(editable=False))

        unit_label = QLabel(unit)
        unit_label.setFont(theme.get_font(size=10))
        unit_label.setStyleSheet(f"color: {theme.TEXT_FAINT};")

        self._threshold_inputs[key] = field

        h.addWidget(label)
        h.addWidget(field)
        h.addWidget(unit_label)
        h.addStretch()

        return row

    def _build_pin_section(self) -> QFrame:
        """Section card for PIN management."""
        card = self._make_card()
        layout = card.layout()

        section_title = QLabel("Admin PIN")
        section_title.setFont(theme.get_font(bold=True, size=13))
        section_title.setStyleSheet(f"color: {theme.TEXT};")
        layout.addWidget(section_title)
        layout.addWidget(self._make_divider())

        # Status row
        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 4, 0, 4)

        self._pin_status_label = QLabel()
        self._pin_status_label.setFont(theme.get_font(size=11))
        self._pin_status_label.setStyleSheet(f"color: {theme.TEXT_DIM};")

        self._set_pin_btn   = theme.make_ghost_button("SET PIN")
        self._change_pin_btn = theme.make_ghost_button("CHANGE PIN")
        self._set_pin_btn.setFixedHeight(32)
        self._change_pin_btn.setFixedHeight(32)
        self._set_pin_btn.clicked.connect(self._on_set_pin)
        self._change_pin_btn.clicked.connect(self._on_change_pin)

        status_row.addWidget(self._pin_status_label)
        status_row.addStretch()
        status_row.addWidget(self._set_pin_btn)
        status_row.addWidget(self._change_pin_btn)

        layout.addLayout(status_row)

        return card

    def _build_override_log_section(self) -> QFrame:
        """Section card with override log table."""
        card = self._make_card()
        layout = card.layout()

        section_title = QLabel("Override Log")
        section_title.setFont(theme.get_font(bold=True, size=13))
        section_title.setStyleSheet(f"color: {theme.TEXT};")
        layout.addWidget(section_title)
        layout.addWidget(self._make_divider())

        self._log_table = QTableWidget()
        self._log_table.setColumnCount(len(OVERRIDE_HEADERS))
        self._log_table.setHorizontalHeaderLabels(OVERRIDE_HEADERS)
        self._log_table.setFont(theme.get_font(size=10))
        self._log_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._log_table.setShowGrid(True)
        self._log_table.verticalHeader().setVisible(False)
        self._log_table.setSortingEnabled(True)
        self._log_table.setMinimumHeight(200)

        header = self._log_table.horizontalHeader()
        header.setSectionResizeMode(COL_TIMESTAMP,  QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_BATTERY_ID, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_ACTION,     QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self._log_table)

        return card

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def refresh(self) -> None:
        """Reload all settings data from the database."""
        self._load_thresholds()
        self._load_pin_status()
        self._load_override_log()

    # -------------------------------------------------------------------------
    # Slot handlers
    # -------------------------------------------------------------------------

    def _on_unlock_clicked(self) -> None:
        """Prompt for PIN; if correct, enable threshold editing."""
        if self._is_unlocked:
            # Lock back down
            self._lock()
            return

        if not admin_service.pin_is_set():
            QMessageBox.information(
                self,
                "No PIN Set",
                "No admin PIN has been configured yet.\nSet a PIN first to lock settings.",
            )
            return

        dlg = PinDialog(self)
        if dlg.exec():
            self._unlock()

    def _on_save_thresholds(self) -> None:
        """Write all edited threshold values back to the database."""
        errors: list[str] = []

        for key, label_text, _unit in THRESHOLD_FIELDS:
            field = self._threshold_inputs[key]
            raw = field.text().strip()
            if not raw:
                continue
            try:
                float(raw)   # basic numeric validation
            except ValueError:
                errors.append(f"'{label_text}': must be a number.")
                continue
            try:
                admin_service.update_threshold(key, raw)
            except Exception as e:
                errors.append(f"'{label_text}': {e}")

        if errors:
            QMessageBox.warning(
                self, "Save Errors",
                "Some values could not be saved:\n\n" + "\n".join(errors),
            )
        else:
            QMessageBox.information(self, "Saved", "Threshold settings saved successfully.")

        # Reload to show persisted values
        self._load_thresholds()

    def _on_set_pin(self) -> None:
        """Open SetPinDialog to create a new PIN (no existing PIN required)."""
        dlg = SetPinDialog(is_change=False, parent=self)
        if dlg.exec():
            self._load_pin_status()
            QMessageBox.information(self, "PIN Set", "Admin PIN has been set.")

    def _on_change_pin(self) -> None:
        """Open SetPinDialog to change the existing PIN (requires old PIN)."""
        dlg = SetPinDialog(is_change=True, parent=self)
        if dlg.exec():
            self._load_pin_status()
            QMessageBox.information(self, "PIN Changed", "Admin PIN has been updated.")

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _unlock(self) -> None:
        """Switch threshold fields to edit mode."""
        self._is_unlocked = True
        self._unlock_btn.setText("🔓  LOCK SETTINGS")

        for field in self._threshold_inputs.values():
            field.setReadOnly(False)
            field.setStyleSheet(self._field_style(editable=True))

        self._save_btn.setVisible(True)

    def _lock(self) -> None:
        """Switch threshold fields back to read-only mode."""
        self._is_unlocked = False
        self._unlock_btn.setText("🔒  UNLOCK SETTINGS")

        for field in self._threshold_inputs.values():
            field.setReadOnly(True)
            field.setStyleSheet(self._field_style(editable=False))

        self._save_btn.setVisible(False)

    def _load_thresholds(self) -> None:
        """Populate threshold fields from admin_service.get_all_settings()."""
        settings = admin_service.get_all_settings()
        for key, _label, _unit in THRESHOLD_FIELDS:
            field = self._threshold_inputs.get(key)
            if field is not None:
                field.setText(settings.get(key, ""))

    def _load_pin_status(self) -> None:
        """Update PIN section labels and button visibility."""
        is_set = admin_service.pin_is_set()
        if is_set:
            self._pin_status_label.setText("PIN status:  ✓  Configured")
            self._pin_status_label.setStyleSheet(f"color: {theme.GREEN};")
            self._set_pin_btn.setVisible(False)
            self._change_pin_btn.setVisible(True)
        else:
            self._pin_status_label.setText("PIN status:  ✗  Not set")
            self._pin_status_label.setStyleSheet(f"color: {theme.TEXT_DIM};")
            self._set_pin_btn.setVisible(True)
            self._change_pin_btn.setVisible(False)

    def _load_override_log(self) -> None:
        """Populate the override log table from the database."""
        logs = override_dal.get_all_override_logs()

        self._log_table.setSortingEnabled(False)
        self._log_table.setRowCount(0)

        for log in logs:
            row_idx = self._log_table.rowCount()
            self._log_table.insertRow(row_idx)

            ts_text  = log.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            bat_text = str(log.battery_id)
            act_text = log.action_description

            self._log_table.setItem(row_idx, COL_TIMESTAMP,  _ro_item(ts_text))
            self._log_table.setItem(row_idx, COL_BATTERY_ID, _ro_item(bat_text))
            self._log_table.setItem(row_idx, COL_ACTION,     _ro_item(act_text))

        self._log_table.setSortingEnabled(True)
        self._log_table.resizeRowsToContents()

    # -------------------------------------------------------------------------
    # Style helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _field_style(editable: bool) -> str:
        if editable:
            return (
                f"QLineEdit {{"
                f"  background-color: {theme.BG3};"
                f"  color: {theme.TEXT};"
                f"  border: 1px solid {theme.ORANGE};"
                f"  border-radius: 4px;"
                f"  padding: 2px 6px;"
                f"}}"
            )
        return (
            f"QLineEdit {{"
            f"  background-color: {theme.BG2};"
            f"  color: {theme.TEXT_DIM};"
            f"  border: 1px solid {theme.BORDER};"
            f"  border-radius: 4px;"
            f"  padding: 2px 6px;"
            f"}}"
        )

    @staticmethod
    def _make_card() -> QFrame:
        """Return a styled card frame with a vertical QVBoxLayout."""
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{"
            f"  background-color: {theme.BG2};"
            f"  border: 1px solid {theme.BORDER};"
            f"  border-radius: 8px;"
            f"}}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)
        return card

    @staticmethod
    def _make_divider() -> QFrame:
        """Return a thin horizontal rule for section separation."""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {theme.BORDER}; border: none;")
        return line


# -------------------------------------------------------------------------
# Module-level helpers
# -------------------------------------------------------------------------

def _ro_item(text: str) -> QTableWidgetItem:
    """Return a non-editable, vertically centered QTableWidgetItem."""
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    return item
