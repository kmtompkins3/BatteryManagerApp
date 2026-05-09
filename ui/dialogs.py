"""
dialogs.py — Modal dialogs for the FRC Battery Manager UI.

All dialogs inherit QDialog and use the dark STR brand theme.
Import with: from ui.dialogs import BeakReadingsDialog, AddBatteryDialog, ...
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QCheckBox, QFrame, QWidget, QApplication,
    QListWidget, QAbstractItemView,
)
from PyQt6.QtCore import Qt
from datetime import date
from PyQt6.QtGui import QFont
from ui import theme
import app.services.admin_service as admin_service
from app.exceptions import PinNotSetError, InvalidPinError


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _dialog_header(dialog: QDialog, title: str, accent: str = None) -> QVBoxLayout:
    """Set up a dialog with a branded title bar. Returns the content VBoxLayout."""
    if accent is None:
        accent = theme.ORANGE
    dialog.setModal(True)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    # Top accent bar
    top_bar = QWidget()
    top_bar.setFixedHeight(3)
    top_bar.setStyleSheet(f"background: {accent};")
    layout.addWidget(top_bar)

    # Header row
    header = QWidget()
    header.setStyleSheet(f"background: {theme.BG2};")
    h_layout = QHBoxLayout(header)
    h_layout.setContentsMargins(20, 14, 14, 14)

    title_label = QLabel(title.upper())
    title_label.setFont(theme.get_font(bold=True, size=12))
    title_label.setStyleSheet(f"color: {theme.TEXT};")
    h_layout.addWidget(title_label)
    h_layout.addStretch()

    close_btn = QPushButton("×")
    close_btn.setFixedSize(28, 28)
    close_btn.setStyleSheet(
        f"background: transparent; color: {theme.TEXT_DIM}; border: none; font-size: 16px;"
    )
    close_btn.clicked.connect(dialog.reject)
    h_layout.addWidget(close_btn)
    layout.addWidget(header)

    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setStyleSheet(f"color: {theme.BORDER};")
    layout.addWidget(sep)

    content = QVBoxLayout()
    content.setContentsMargins(22, 20, 22, 20)
    content.setSpacing(14)
    layout.addLayout(content)
    return content


def _make_field_label(text: str) -> QLabel:
    """Return a small-caps dim label above an input field."""
    lbl = QLabel(text.upper())
    lbl.setFont(theme.get_font(size=9))
    lbl.setStyleSheet(f"color: {theme.TEXT_DIM};")
    return lbl


# ---------------------------------------------------------------------------
# BeakReadingsDialog
# ---------------------------------------------------------------------------

class BeakReadingsDialog(QDialog):
    """Collects beak readings (Voltage, Charge%, Resistance) before a scan-out."""

    def __init__(self, battery_id: int, parent=None):
        super().__init__(parent)
        self._battery_id = battery_id
        self.voltage: float = 0.0
        self.charge_pct: int = 0
        self.resistance_mohm: float = 0.0

        self.setWindowTitle(f"Scan-Out — Battery #{battery_id}")
        self.setMinimumWidth(480)
        self.setStyleSheet(f"background: {theme.BG2};")

        content = _dialog_header(
            self,
            f"SCAN-OUT · BATTERY #{battery_id}",
            accent=theme.ORANGE,
        )

        # Sub-label
        sub = QLabel("Beak readings required before this battery goes on field.")
        sub.setFont(theme.get_font(size=10))
        sub.setStyleSheet(f"color: {theme.TEXT_DIM};")
        sub.setWordWrap(True)
        content.addWidget(sub)

        # Three input fields side by side
        fields_row = QHBoxLayout()
        fields_row.setSpacing(12)

        self._voltage_edit = self._make_reading_field(
            fields_row, "Voltage", "V", "12.50"
        )
        self._charge_edit = self._make_reading_field(
            fields_row, "Charge", "%", "88"
        )
        self._resistance_edit = self._make_reading_field(
            fields_row, "Resistance", "mΩ", "13.0"
        )
        content.addLayout(fields_row)

        # Error label (hidden until validation fails)
        self._error_label = QLabel("")
        self._error_label.setFont(theme.get_font(size=9))
        self._error_label.setStyleSheet(f"color: {theme.RED};")
        self._error_label.setVisible(False)
        content.addWidget(self._error_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = theme.make_ghost_button("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        confirm_btn = theme.make_primary_button("CONFIRM SCAN-OUT →", color=theme.ORANGE)
        confirm_btn.clicked.connect(self._on_confirm)
        btn_row.addWidget(confirm_btn)
        content.addLayout(btn_row)

    def _make_reading_field(
        self,
        parent_layout: QHBoxLayout,
        label: str,
        unit: str,
        default: str,
    ) -> QLineEdit:
        """Add a labeled input field with a unit suffix to a horizontal layout."""
        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(_make_field_label(label))

        row = QHBoxLayout()
        row.setSpacing(4)
        edit = QLineEdit(default)
        edit.setFont(theme.get_font(size=13))
        edit.setFixedHeight(40)
        row.addWidget(edit)

        unit_lbl = QLabel(unit)
        unit_lbl.setFont(theme.get_font(size=10))
        unit_lbl.setStyleSheet(f"color: {theme.TEXT_DIM};")
        row.addWidget(unit_lbl)
        col.addLayout(row)
        parent_layout.addLayout(col)
        return edit

    def _on_confirm(self):
        """Validate all fields and accept if valid."""
        voltage_text = self._voltage_edit.text().strip()
        charge_text = self._charge_edit.text().strip()
        resistance_text = self._resistance_edit.text().strip()

        try:
            voltage = float(voltage_text)
            charge = int(charge_text)
            resistance = float(resistance_text)
            if voltage <= 0 or charge < 0 or resistance <= 0:
                raise ValueError("Values must be positive.")
        except ValueError:
            self._error_label.setText(
                "All fields must contain valid positive numbers."
            )
            self._error_label.setVisible(True)
            return

        self.voltage = voltage
        self.charge_pct = charge
        self.resistance_mohm = resistance
        self._error_label.setVisible(False)
        self.accept()


# ---------------------------------------------------------------------------
# AddBatteryDialog
# ---------------------------------------------------------------------------

class AddBatteryDialog(QDialog):
    """Dialog for adding a new battery to the system."""

    BRANDS = ["MK Battery", "EnerSys", "Power-Sonic", "Duracell"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.brand: str = ""
        self.batch_number: str = ""
        self.purchase_date: str | None = None
        self.broken_in: bool = False

        self.setWindowTitle("Add Battery")
        self.setMinimumWidth(400)
        self.setStyleSheet(f"background: {theme.BG2};")

        content = _dialog_header(self, "ADD BATTERY", accent=theme.PURPLE)

        # Brand
        content.addWidget(_make_field_label("Brand"))
        self._brand_combo = QComboBox()
        self._brand_combo.addItems(self.BRANDS)
        self._brand_combo.setFont(theme.get_font(size=11))
        content.addWidget(self._brand_combo)

        # Batch Number
        content.addWidget(_make_field_label("Batch Number"))
        self._batch_edit = QLineEdit()
        self._batch_edit.setPlaceholderText("e.g. B-2026-A")
        self._batch_edit.setFont(theme.get_font(size=11))
        self._batch_edit.textChanged.connect(self._update_button_state)
        content.addWidget(self._batch_edit)

        # Purchase Date
        content.addWidget(_make_field_label("Purchase Date"))
        self._date_edit = QLineEdit()
        self._date_edit.setPlaceholderText("YYYY-MM-DD (optional)")
        self._date_edit.setFont(theme.get_font(size=11))
        content.addWidget(self._date_edit)

        # Broken In checkbox
        self._broken_in_check = QCheckBox("Battery has been broken in")
        self._broken_in_check.setFont(theme.get_font(size=10))
        self._broken_in_check.setStyleSheet(
            f"color: {theme.TEXT};"
            f"QCheckBox::indicator:checked {{ background: {theme.PURPLE};"
            f" border: 1px solid {theme.PURPLE}; }}"
        )
        self._broken_in_check.stateChanged.connect(self._update_button_state)
        content.addWidget(self._broken_in_check)

        # Error label
        self._error_label = QLabel("")
        self._error_label.setFont(theme.get_font(size=9))
        self._error_label.setStyleSheet(f"color: {theme.RED};")
        self._error_label.setVisible(False)
        content.addWidget(self._error_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = theme.make_ghost_button("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self._create_btn = theme.make_primary_button(
            "CREATE BATTERY →", color=theme.PURPLE
        )
        self._create_btn.setEnabled(False)
        self._create_btn.clicked.connect(self._on_create)
        btn_row.addWidget(self._create_btn)
        content.addLayout(btn_row)

    def _update_button_state(self):
        """Enable the create button only when required fields are filled."""
        batch_ok = bool(self._batch_edit.text().strip())
        broken_in_ok = self._broken_in_check.isChecked()
        self._create_btn.setEnabled(batch_ok and broken_in_ok)

    def _on_create(self):
        """Collect field values and accept the dialog."""
        self.brand = self._brand_combo.currentText()
        self.batch_number = self._batch_edit.text().strip()
        date_text = self._date_edit.text().strip()
        self.purchase_date = date_text if date_text else None
        self.broken_in = self._broken_in_check.isChecked()
        self.accept()


# ---------------------------------------------------------------------------
# PinDialog
# ---------------------------------------------------------------------------

class PinDialog(QDialog):
    """Prompts the user to enter the admin PIN for verification."""

    def __init__(self, title: str = "ADMIN PIN REQUIRED", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(360)
        self.setStyleSheet(f"background: {theme.BG2};")

        content = _dialog_header(self, title, accent=theme.ORANGE)

        # Check whether a PIN has been set at all
        if not admin_service.pin_is_set():
            msg = QLabel(
                "No PIN has been set. Go to Settings to create one."
            )
            msg.setFont(theme.get_font(size=10))
            msg.setStyleSheet(f"color: {theme.TEXT_DIM};")
            msg.setWordWrap(True)
            content.addWidget(msg)

            ok_btn = theme.make_ghost_button("OK")
            ok_btn.clicked.connect(self.reject)
            btn_row = QHBoxLayout()
            btn_row.addStretch()
            btn_row.addWidget(ok_btn)
            content.addLayout(btn_row)
            return

        # Normal flow
        msg = QLabel("Enter the admin PIN to continue.")
        msg.setFont(theme.get_font(size=10))
        msg.setStyleSheet(f"color: {theme.TEXT_DIM};")
        content.addWidget(msg)

        self._pin_edit = QLineEdit()
        self._pin_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._pin_edit.setMaxLength(20)
        self._pin_edit.setFont(theme.get_font(size=13))
        self._pin_edit.setPlaceholderText("PIN")
        self._pin_edit.returnPressed.connect(self._on_confirm)
        content.addWidget(self._pin_edit)

        self._error_label = QLabel("Incorrect PIN.")
        self._error_label.setFont(theme.get_font(size=9))
        self._error_label.setStyleSheet(f"color: {theme.RED};")
        self._error_label.setVisible(False)
        content.addWidget(self._error_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = theme.make_ghost_button("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        confirm_btn = theme.make_primary_button("CONFIRM", color=theme.ORANGE)
        confirm_btn.clicked.connect(self._on_confirm)
        btn_row.addWidget(confirm_btn)
        content.addLayout(btn_row)

    def get_pin(self) -> str:
        """Returns the text currently in the PIN field."""
        if hasattr(self, "_pin_edit"):
            return self._pin_edit.text()
        return ""

    def _on_confirm(self):
        """Verify the PIN; accept on success or show error on failure."""
        try:
            if admin_service.verify_pin(self._pin_edit.text()):
                self._error_label.setVisible(False)
                self.accept()
            else:
                self._error_label.setVisible(True)
                self._pin_edit.clear()
                self._pin_edit.setFocus()
        except PinNotSetError:
            self._error_label.setText("No PIN configured.")
            self._error_label.setVisible(True)


# ---------------------------------------------------------------------------
# SetPinDialog
# ---------------------------------------------------------------------------

class SetPinDialog(QDialog):
    """Dialog for creating or changing the admin PIN."""

    def __init__(self, is_change: bool = False, parent=None):
        super().__init__(parent)
        self._is_change = is_change
        title = "CHANGE PIN" if is_change else "SET ADMIN PIN"
        self.setWindowTitle(title)
        self.setMinimumWidth(380)
        self.setStyleSheet(f"background: {theme.BG2};")

        content = _dialog_header(self, title, accent=theme.ORANGE)

        if is_change:
            content.addWidget(_make_field_label("Current PIN"))
            self._current_edit = QLineEdit()
            self._current_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._current_edit.setFont(theme.get_font(size=13))
            content.addWidget(self._current_edit)
        else:
            self._current_edit = None

        content.addWidget(_make_field_label("New PIN"))
        self._new_edit = QLineEdit()
        self._new_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._new_edit.setFont(theme.get_font(size=13))
        content.addWidget(self._new_edit)

        content.addWidget(_make_field_label("Confirm PIN"))
        self._confirm_edit = QLineEdit()
        self._confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_edit.setFont(theme.get_font(size=13))
        self._confirm_edit.returnPressed.connect(self._on_save)
        content.addWidget(self._confirm_edit)

        self._error_label = QLabel("")
        self._error_label.setFont(theme.get_font(size=9))
        self._error_label.setStyleSheet(f"color: {theme.RED};")
        self._error_label.setVisible(False)
        content.addWidget(self._error_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = theme.make_ghost_button("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = theme.make_primary_button("SAVE PIN →", color=theme.ORANGE)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)
        content.addLayout(btn_row)

    def _on_save(self):
        """Validate fields and call the appropriate admin_service function."""
        new_pin = self._new_edit.text()
        confirm_pin = self._confirm_edit.text()

        if not new_pin:
            self._show_error("New PIN cannot be empty.")
            return
        if new_pin != confirm_pin:
            self._show_error("PINs do not match.")
            return

        try:
            if self._is_change and self._current_edit is not None:
                admin_service.change_pin(self._current_edit.text(), new_pin)
            else:
                admin_service.set_pin(new_pin)
            self.accept()
        except InvalidPinError:
            self._show_error("Current PIN is incorrect.")

    def _show_error(self, message: str):
        self._error_label.setText(message)
        self._error_label.setVisible(True)


# ---------------------------------------------------------------------------
# WrongBatteryDialog
# ---------------------------------------------------------------------------

class WrongBatteryDialog(QDialog):
    """Warns that the wrong battery was scanned in competition mode."""

    def __init__(self, scanned_id: int, correct_id: int, parent=None):
        super().__init__(parent)
        self.override_accepted: bool = False
        self.setWindowTitle("Wrong Battery Scanned")
        self.setMinimumWidth(440)
        self.setStyleSheet(f"background: {theme.BG2};")

        content = _dialog_header(self, "WRONG BATTERY", accent=theme.RED)

        # Warning icon + message
        warning_row = QHBoxLayout()
        icon_label = QLabel("⚠")
        icon_label.setFont(theme.get_font(bold=True, size=28))
        icon_label.setStyleSheet(f"color: {theme.RED};")
        icon_label.setFixedWidth(44)
        warning_row.addWidget(icon_label)

        warn_text = QLabel("BATTERY MISMATCH — COMPETITION MODE")
        warn_text.setFont(theme.get_font(bold=True, size=12))
        warn_text.setStyleSheet(f"color: {theme.RED};")
        warn_text.setWordWrap(True)
        warning_row.addWidget(warn_text)
        content.addLayout(warning_row)

        detail = QLabel(
            f"The next battery in queue is #{correct_id}. "
            f"You scanned #{scanned_id}."
        )
        detail.setFont(theme.get_font(size=11))
        detail.setStyleSheet(f"color: {theme.TEXT};")
        detail.setWordWrap(True)
        content.addWidget(detail)

        btn_row = QHBoxLayout()
        cancel_btn = theme.make_ghost_button("Cancel Scan")
        cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()

        override_btn = theme.make_danger_button("OVERRIDE — PROCEED ANYWAY")
        override_btn.clicked.connect(self._on_override)
        btn_row.addWidget(override_btn)
        content.addLayout(btn_row)

    def _on_cancel(self):
        self.override_accepted = False
        self.reject()

    def _on_override(self):
        self.override_accepted = True
        self.accept()


# ---------------------------------------------------------------------------
# ConfirmDialog
# ---------------------------------------------------------------------------

class ConfirmDialog(QDialog):
    """Generic yes/no confirmation dialog."""

    def __init__(
        self,
        title: str,
        message: str,
        confirm_text: str = "CONFIRM",
        accent: str = None,
        parent=None,
    ):
        super().__init__(parent)
        if accent is None:
            accent = theme.ORANGE
        self.setWindowTitle(title)
        self.setMinimumWidth(380)
        self.setStyleSheet(f"background: {theme.BG2};")

        content = _dialog_header(self, title, accent=accent)

        msg_label = QLabel(message)
        msg_label.setFont(theme.get_font(size=10))
        msg_label.setStyleSheet(f"color: {theme.TEXT};")
        msg_label.setWordWrap(True)
        content.addWidget(msg_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = theme.make_ghost_button("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        confirm_btn = theme.make_primary_button(confirm_text, color=accent)
        confirm_btn.clicked.connect(self.accept)
        btn_row.addWidget(confirm_btn)
        content.addLayout(btn_row)


# ---------------------------------------------------------------------------
# EditBatteryDialog
# ---------------------------------------------------------------------------

class EditBatteryDialog(QDialog):
    """PIN-gated dialog for editing an existing battery's Brand, Batch Number, and Purchase Date."""

    def __init__(self, battery_id: int, parent=None):
        super().__init__(parent)
        # Lazy import to avoid circular imports
        from app.services.battery_service import get_battery, update_battery

        self._battery_id = battery_id
        self._update_battery = update_battery

        battery = get_battery(battery_id)

        # Public output properties
        self.brand: str = battery.brand
        self.batch_number: str = battery.batch_number
        self.purchase_date: str = (
            battery.purchase_date.isoformat() if battery.purchase_date else ""
        )

        self.setWindowTitle(f"Edit Battery #{battery_id}")
        self.setMinimumWidth(420)
        self.setStyleSheet(f"background: {theme.BG2};")

        content = _dialog_header(self, f"EDIT BATTERY #{battery_id}", accent=theme.ORANGE)

        # Read-only info line
        info_label = QLabel(
            f"Battery ID: {battery_id}  ·  Added: {battery.date_added.strftime('%Y-%m-%d')}"
        )
        info_label.setFont(theme.get_font(size=10))
        info_label.setStyleSheet(f"color: {theme.TEXT_DIM};")
        content.addWidget(info_label)

        # Brand field
        content.addWidget(_make_field_label("Brand"))
        self._brand_edit = QLineEdit(battery.brand)
        self._brand_edit.setFont(theme.get_font(size=11))
        self._brand_edit.textChanged.connect(self._update_save_btn)
        content.addWidget(self._brand_edit)

        # Batch Number field
        content.addWidget(_make_field_label("Batch Number"))
        self._batch_edit = QLineEdit(battery.batch_number)
        self._batch_edit.setFont(theme.get_font(size=11))
        self._batch_edit.textChanged.connect(self._update_save_btn)
        content.addWidget(self._batch_edit)

        # Purchase Date field
        purchase_date_str = (
            battery.purchase_date.isoformat() if battery.purchase_date else ""
        )
        content.addWidget(_make_field_label("Purchase Date"))
        self._date_edit = QLineEdit(purchase_date_str)
        self._date_edit.setPlaceholderText("YYYY-MM-DD")
        self._date_edit.setFont(theme.get_font(size=11))
        content.addWidget(self._date_edit)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = theme.make_ghost_button("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self._save_btn = theme.make_primary_button("SAVE CHANGES")
        self._save_btn.setFixedHeight(36)
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._save_btn)
        content.addLayout(btn_row)

        # Set initial button state
        self._update_save_btn()

    def _update_save_btn(self):
        """Enable Save only when Brand and Batch Number are non-empty."""
        brand_ok = bool(self._brand_edit.text().strip())
        batch_ok = bool(self._batch_edit.text().strip())
        self._save_btn.setEnabled(brand_ok and batch_ok)

    def _on_save(self):
        """Validate the date field, then persist changes and close."""
        from PyQt6.QtWidgets import QMessageBox

        brand = self._brand_edit.text().strip()
        batch = self._batch_edit.text().strip()
        date_text = self._date_edit.text().strip()

        purchase_date_value = None
        if date_text:
            try:
                purchase_date_value = date.fromisoformat(date_text)
            except ValueError:
                QMessageBox.warning(
                    self,
                    "Invalid Date",
                    f"'{date_text}' is not a valid date. Use YYYY-MM-DD format.",
                )
                return

        self._update_battery(self._battery_id, brand, batch, purchase_date_value)

        # Update public properties before accepting
        self.brand = brand
        self.batch_number = batch
        self.purchase_date = date_text
        self.accept()


# ---------------------------------------------------------------------------
# AlreadyOnFieldDialog
# ---------------------------------------------------------------------------

class AlreadyOnFieldDialog(QDialog):
    """
    Shown in Practice mode when a battery that already has an open session is scanned.
    Operator chooses: SCAN IN (normal close-session) or RESET SESSION START (override, re-scan-out).
    """

    def __init__(self, battery_id: int, parent=None):
        super().__init__(parent)
        self.choice: str = ""

        self.setWindowTitle(f"Battery #{battery_id} — Already On Field")
        self.setMinimumWidth(440)
        self.setStyleSheet(f"background: {theme.BG2};")

        content = _dialog_header(
            self,
            f"BATTERY #{battery_id} — ALREADY ON FIELD",
            accent=theme.ORANGE,
        )

        # Body message
        body = QLabel(
            f"Battery #{battery_id} is currently marked OnField.\nChoose an action:"
        )
        body.setFont(theme.get_font(size=11))
        body.setStyleSheet(f"color: {theme.TEXT};")
        body.setWordWrap(True)
        content.addWidget(body)

        # Action buttons
        btn_row = QHBoxLayout()

        scan_in_btn = theme.make_primary_button("SCAN IN")
        scan_in_btn.clicked.connect(self._on_scan_in)
        btn_row.addWidget(scan_in_btn)

        reset_btn = theme.make_ghost_button("RESET SESSION START")
        reset_btn.clicked.connect(self._on_reset_start)
        btn_row.addWidget(reset_btn)

        content.addLayout(btn_row)

    def _on_scan_in(self):
        """Normal scan-in: close the existing session."""
        self.choice = "scan_in"
        self.accept()

    def _on_reset_start(self):
        """Override: close old session and start a new one with fresh beak readings."""
        self.choice = "reset_start"
        self.accept()


# ---------------------------------------------------------------------------
# AddToQueueDialog
# ---------------------------------------------------------------------------

class AddToQueueDialog(QDialog):
    """Lets the operator pick one or more batteries to add to the competition queue."""

    def __init__(self, available_batteries: list, parent=None):
        super().__init__(parent)
        self.selected_battery_ids: list[int] = []

        self.setWindowTitle("Add Battery to Queue")
        self.setMinimumWidth(400)
        self.setStyleSheet(f"background: {theme.BG2};")

        content = _dialog_header(self, "ADD BATTERY TO QUEUE", accent=theme.PURPLE)

        if not available_batteries:
            msg = QLabel("All active batteries are already in the queue.")
            msg.setFont(theme.get_font(size=10))
            msg.setStyleSheet(f"color: {theme.TEXT_DIM};")
            msg.setWordWrap(True)
            content.addWidget(msg)
            ok_btn = theme.make_ghost_button("OK")
            ok_btn.clicked.connect(self.reject)
            row = QHBoxLayout()
            row.addStretch()
            row.addWidget(ok_btn)
            content.addLayout(row)
            return

        hint = QLabel("Hold Ctrl (or Cmd) to select multiple batteries.")
        hint.setFont(theme.get_font(size=9))
        hint.setStyleSheet(f"color: {theme.TEXT_DIM};")
        content.addWidget(hint)

        content.addWidget(_make_field_label("Select Batteries"))
        self._list = QListWidget()
        self._list.setFont(theme.get_font(size=11))
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._list.setMinimumHeight(140)
        for b in available_batteries:
            label = f"#{b.battery_id}  —  {b.brand}  ·  Batch {b.batch_number}"
            item = self._list.addItem(label)
            self._list.item(self._list.count() - 1).setData(Qt.ItemDataRole.UserRole, b.battery_id)
        content.addWidget(self._list)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = theme.make_ghost_button("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        add_btn = theme.make_primary_button("ADD TO QUEUE →", color=theme.PURPLE)
        add_btn.clicked.connect(self._on_add)
        btn_row.addWidget(add_btn)
        content.addLayout(btn_row)

    def _on_add(self):
        self.selected_battery_ids = [
            item.data(Qt.ItemDataRole.UserRole)
            for item in self._list.selectedItems()
        ]
        if self.selected_battery_ids:
            self.accept()
