"""MainWindow — top-level application window for the FRC Battery Manager.

Holds a fixed 240px sidebar with navigation and a QStackedWidget on the right
for all four views (Home, Competition, Statistics, Settings).
Also installs a USB HID barcode-scanner event filter so the app can react to
scans regardless of which widget currently has focus.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QStackedWidget, QLabel, QFrame, QLineEdit, QComboBox,
    QTextEdit, QApplication,
)
from PyQt6.QtCore import Qt, QObject, QTimer, QEvent, pyqtSignal
from PyQt6.QtGui import QFont

from ui import theme
from ui.home_view import HomeView
from ui.competition_view import CompetitionView
from ui.stats_view import StatsView
from ui.settings_view import SettingsView
from app.state import AppState
from app.constants import AppMode

# Index constants for the QStackedWidget pages
PAGE_HOME        = 0
PAGE_COMPETITION = 1
PAGE_STATS       = 2
PAGE_SETTINGS    = 3


# ---------------------------------------------------------------------------
# Scanner event filter
# ---------------------------------------------------------------------------

class ScannerFilter(QObject):
    """
    Intercepts keyboard events to detect USB HID barcode scanner input.

    A scanner emits digit keystrokes very rapidly, then sends Enter.
    This filter accumulates digits and emits scan_received when Enter
    is pressed — but only when a text input widget does NOT have focus.
    """

    scan_received = pyqtSignal(str)  # emits the accumulated digit string

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self._buffer = ""

        # Clear the buffer if no Enter arrives within 800 ms
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(800)
        self._timer.timeout.connect(self._clear_buffer)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Accumulate digit keystrokes; emit on Enter. Pass all other events through."""
        if event.type() == QEvent.Type.KeyPress:
            focused = QApplication.focusWidget()
            # Let normal input widgets keep their own key handling
            if isinstance(focused, (QLineEdit, QComboBox, QTextEdit)):
                return False
            key = event.text()
            if key.isdigit():
                self._buffer += key
                self._timer.start()   # restart the 800 ms window
                return True
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self._buffer:
                    self.scan_received.emit(self._buffer)
                    self._buffer = ""
                    self._timer.stop()
                    return True
        return False

    def _clear_buffer(self) -> None:
        """Discard a partial buffer that never received an Enter keystroke."""
        self._buffer = ""


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    """
    Top-level window.  Left sidebar handles navigation; right panel shows
    the active view.  A scanner filter drives the scan workflow.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FRC Battery Manager")
        self.setMinimumSize(1100, 720)
        self._setup_ui()
        self._setup_scanner()
        self._connect_signals()
        self._home_view.refresh()   # populate the table on first load

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Build the two-column layout: sidebar (left) + content area (right)."""
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Horizontal split: sidebar | content
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        body_layout.addWidget(self._build_sidebar())
        body_layout.addWidget(self._build_content_area(), stretch=1)

        root_layout.addWidget(body, stretch=1)
        root_layout.addWidget(self._build_status_bar())

    def _build_sidebar(self) -> QWidget:
        """Return the fixed-width left sidebar."""
        sidebar = QWidget()
        sidebar.setFixedWidth(290)  # SIDEBAR WIDTH — change this value to resize the sidebar
        sidebar.setStyleSheet(
            f"background-color: {theme.BG}; "
            f"border-right: 1px solid {theme.BORDER};"
        )

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_sidebar_header())
        layout.addWidget(self._build_nav_section(), stretch=1)
        layout.addWidget(self._build_mode_badge())
        layout.addWidget(self._build_sidebar_footer())

        return sidebar

    def _build_sidebar_header(self) -> QWidget:
        """Return the branded header block at the top of the sidebar."""
        header = QWidget()
        header.setStyleSheet(f"background-color: {theme.BG};")

        layout = QVBoxLayout(header)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(2)

        title_label = QLabel("FRC Battery\nManager")
        title_label.setFont(theme.get_font(bold=True, size=16))
        title_label.setStyleSheet(f"color: {theme.TEXT};")

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet(f"color: {theme.BORDER};")

        subtitle_label = QLabel("Usage · Health · Performance")
        subtitle_label.setFont(theme.get_font(size=10))
        subtitle_label.setStyleSheet(f"color: {theme.TEXT_DIM};")

        layout.addWidget(title_label)
        layout.addWidget(divider)
        layout.addWidget(subtitle_label)

        return header

    def _build_nav_section(self) -> QWidget:
        """Return the vertical stack of navigation buttons."""
        nav_widget = QWidget()
        nav_widget.setStyleSheet(f"background-color: {theme.BG};")

        layout = QVBoxLayout(nav_widget)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(2)

        # Build the four nav buttons and keep references for active-state tracking
        self._nav_home = self._make_nav_button("▬  Home")
        self._nav_comp = self._make_nav_button("≣  Competition")
        self._nav_stats = self._make_nav_button("↗  Statistics")

        # The LIVE badge is a child label on the Competition button
        self._live_badge = QLabel("LIVE ●")
        self._live_badge.setFont(theme.get_font(bold=True, size=8))
        self._live_badge.setStyleSheet(
            f"color: {theme.ORANGE}; background: transparent; padding: 0 8px;"
        )
        self._live_badge.setVisible(False)

        # Overlay the LIVE badge on the competition button using an HBox
        comp_row = QWidget()
        comp_row.setStyleSheet("background: transparent;")
        comp_row_layout = QHBoxLayout(comp_row)
        comp_row_layout.setContentsMargins(0, 0, 0, 0)
        comp_row_layout.setSpacing(0)
        comp_row_layout.addWidget(self._nav_comp, stretch=1)
        comp_row_layout.addWidget(self._live_badge)

        layout.addWidget(self._nav_home)
        layout.addWidget(comp_row)
        layout.addWidget(self._nav_stats)
        layout.addStretch()

        # Wire up click handlers
        self._nav_home.clicked.connect(self.show_home)
        self._nav_comp.clicked.connect(self._on_competition_nav_clicked)
        self._nav_stats.clicked.connect(lambda: self._navigate_to(PAGE_STATS))

        # Track all nav buttons for active-state styling
        self._nav_buttons: list[QPushButton] = [
            self._nav_home, self._nav_comp, self._nav_stats,
        ]

        return nav_widget

    def _make_nav_button(self, label: str) -> QPushButton:
        """Return a full-width sidebar nav button with the standard style."""
        btn = QPushButton(label)
        btn.setFont(theme.get_font(size=12))
        btn.setFlat(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_nav_style(btn, active=False)
        return btn

    def _apply_nav_style(self, btn: QPushButton, active: bool) -> None:
        """Apply inactive or active QSS to a sidebar nav button."""
        if active:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {theme.BG3};
                    color: {theme.TEXT};
                    border: none;
                    border-left: 3px solid {theme.ORANGE};
                    padding: 12px 14px;
                    text-align: left;
                    font-weight: bold;
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {theme.TEXT_DIM};
                    border: none;
                    border-left: 3px solid transparent;
                    padding: 12px 14px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: {theme.BG3};
                    color: {theme.TEXT};
                }}
            """)

    def _build_mode_badge(self) -> QWidget:
        """Return the small mode-indicator strip between nav and settings."""
        wrapper = QWidget()
        wrapper.setStyleSheet(f"background-color: {theme.BG};")

        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(16, 8, 16, 8)

        self._mode_badge_label = QLabel("PRACTICE MODE")
        self._mode_badge_label.setFont(theme.get_font(bold=True, size=9))
        self._mode_badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mode_badge_label.setStyleSheet(
            f"color: {theme.GREEN}; "
            f"background-color: rgba(34,197,94,0.10); "
            f"padding: 4px 8px;"
        )

        layout.addWidget(self._mode_badge_label)
        return wrapper

    def _build_sidebar_footer(self) -> QWidget:
        """Return the Settings button separated by a top border."""
        footer = QWidget()
        footer.setStyleSheet(
            f"background-color: {theme.BG}; "
            f"border-top: 1px solid {theme.BORDER};"
        )

        layout = QVBoxLayout(footer)
        layout.setContentsMargins(0, 8, 0, 8)

        self._nav_settings = self._make_nav_button("⚙  Settings")
        self._nav_settings.clicked.connect(self.show_settings)
        self._nav_buttons.append(self._nav_settings)

        layout.addWidget(self._nav_settings)
        return footer

    def _build_content_area(self) -> QWidget:
        """Return the right panel containing the QStackedWidget with all views."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget()

        # Create views and keep references for later method calls
        self._home_view = HomeView()
        self._comp_view = CompetitionView()
        self._stats_view = StatsView()
        self._settings_view = SettingsView()

        self._stack.addWidget(self._home_view)    # index 0
        self._stack.addWidget(self._comp_view)    # index 1
        self._stack.addWidget(self._stats_view)   # index 2
        self._stack.addWidget(self._settings_view)  # index 3

        layout.addWidget(self._stack)
        return container

    def _build_status_bar(self) -> QWidget:
        """Return the slim footer bar showing scanner status and last scan result."""
        bar = QWidget()
        bar.setFixedHeight(36)
        bar.setStyleSheet(f"background-color: {theme.BG2}; border-top: 1px solid {theme.BORDER};")

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        # Left: pulsing green dot + label
        scanner_dot = QLabel("●")
        scanner_dot.setFont(theme.get_font(size=11))
        scanner_dot.setStyleSheet(f"color: {theme.GREEN}; background: transparent;")

        scanner_label = QLabel("SCANNER ACTIVE")
        scanner_label.setFont(theme.get_font(bold=True, size=9))
        scanner_label.setStyleSheet(f"color: {theme.GREEN}; background: transparent;")

        # Center: last scan result message
        self._scan_status_label = QLabel("")
        self._scan_status_label.setFont(theme.get_font(size=10))
        self._scan_status_label.setStyleSheet(f"color: {theme.TEXT_DIM}; background: transparent;")
        self._scan_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Timer to fade the scan status message after 5 seconds
        self._scan_status_timer = QTimer()
        self._scan_status_timer.setSingleShot(True)
        self._scan_status_timer.setInterval(5000)
        self._scan_status_timer.timeout.connect(lambda: self._scan_status_label.setText(""))

        layout.addWidget(scanner_dot)
        layout.addWidget(scanner_label)
        layout.addStretch()
        layout.addWidget(self._scan_status_label, stretch=1)
        layout.addStretch()

        return bar

    # -----------------------------------------------------------------------
    # Scanner setup
    # -----------------------------------------------------------------------

    def _setup_scanner(self) -> None:
        """Create the scanner event filter and install it on the application."""
        self._scanner_filter = ScannerFilter(self)
        self._scanner_filter.scan_received.connect(self._on_scan_received)
        QApplication.instance().installEventFilter(self._scanner_filter)

    # -----------------------------------------------------------------------
    # Signal connections
    # -----------------------------------------------------------------------

    def _connect_signals(self) -> None:
        """Wire up all view signals to MainWindow slots."""
        self._home_view.add_battery_requested.connect(self._show_add_battery_dialog)
        self._home_view.battery_selected.connect(self.show_stats)
        self._home_view.edit_battery_requested.connect(self._on_edit_battery_requested)
        self._home_view.retire_battery_requested.connect(self._on_retire_battery_requested)

        self._comp_view.end_competition_requested.connect(self._confirm_end_competition)
        self._comp_view.set_charging_requested.connect(self._set_battery_charging)
        self._comp_view.set_available_requested.connect(self._set_battery_available)
        self._comp_view.cooling_complete.connect(self._on_cooling_complete)
        self._comp_view.battery_missing.connect(self._on_battery_missing)
        self._comp_view.add_battery_to_queue_requested.connect(self._on_add_battery_to_queue)

    # -----------------------------------------------------------------------
    # Navigation
    # -----------------------------------------------------------------------

    def _navigate_to(self, page_index: int) -> None:
        """Switch the visible page and update active button styling in the sidebar."""
        self._stack.setCurrentIndex(page_index)

        # Map page indexes to their corresponding nav buttons
        page_button_map = {
            PAGE_HOME:        self._nav_home,
            PAGE_COMPETITION: self._nav_comp,
            PAGE_STATS:       self._nav_stats,
            PAGE_SETTINGS:    self._nav_settings,
        }

        for btn in self._nav_buttons:
            self._apply_nav_style(btn, active=False)

        active_btn = page_button_map.get(page_index)
        if active_btn is not None:
            self._apply_nav_style(active_btn, active=True)

    def show_home(self) -> None:
        """Navigate to the Home view."""
        self._navigate_to(PAGE_HOME)

    def show_competition(self) -> None:
        """Navigate to the Competition view."""
        self._navigate_to(PAGE_COMPETITION)

    def show_stats(self, battery_id: int) -> None:
        """Load battery stats and navigate to the Statistics view."""
        self._stats_view.load_battery(battery_id)
        self._navigate_to(PAGE_STATS)

    def show_settings(self) -> None:
        """Navigate to the Settings view and reload its data."""
        self._settings_view.refresh()
        self._navigate_to(PAGE_SETTINGS)

    # -----------------------------------------------------------------------
    # Competition nav button
    # -----------------------------------------------------------------------

    def _on_competition_nav_clicked(self) -> None:
        """
        If in Practice mode, require a PIN before starting a competition.
        If already in Competition mode, just switch to the competition view.
        """
        if AppState().is_competition:
            self.show_competition()
            return

        from ui.dialogs import PinDialog
        pin_dlg = PinDialog(parent=self)
        if pin_dlg.exec():
            from app.services.competition_service import start_competition
            start_competition()
            self._handle_competition_mode_entered()

    # -----------------------------------------------------------------------
    # Mode switching
    # -----------------------------------------------------------------------

    def _handle_competition_mode_entered(self) -> None:
        """Update the sidebar badge, switch view, and start the competition timer."""
        self._update_mode_badge()
        self.show_competition()
        self._comp_view.refresh()
        self._comp_view.start_ticking()

    def _handle_competition_ended(self) -> None:
        """Stop the competition timer, reset the badge, and return to Home."""
        self._comp_view.stop_ticking()
        self._update_mode_badge()
        self.show_home()
        self._home_view.refresh()

    def _update_mode_badge(self) -> None:
        """Redraw the mode badge label to reflect the current AppState mode."""
        if AppState().is_competition:
            self._mode_badge_label.setText("COMPETITION MODE")
            self._mode_badge_label.setStyleSheet(
                f"color: {theme.ORANGE}; "
                f"background-color: rgba(255,66,0,0.10); "
                f"padding: 4px 8px;"
            )
            self._live_badge.setVisible(True)
        else:
            self._mode_badge_label.setText("PRACTICE MODE")
            self._mode_badge_label.setStyleSheet(
                f"color: {theme.GREEN}; "
                f"background-color: rgba(34,197,94,0.10); "
                f"padding: 4px 8px;"
            )
            self._live_badge.setVisible(False)

    # -----------------------------------------------------------------------
    # Scan handling
    # -----------------------------------------------------------------------

    def _on_scan_received(self, raw_id: str) -> None:
        """Route a completed barcode scan to the appropriate action."""
        from app.services.scan_router import handle_scan, ScanResult
        result = handle_scan(raw_id)

        if result.action_taken == "needs_beak_readings":
            self._open_beak_dialog(result.battery_id)

        elif result.action_taken == "scan_in_practice":
            self._home_view.refresh()
            self._show_scan_status(f"Battery #{result.battery_id} scanned in.", ok=True)

        elif result.action_taken == "scan_in_competition":
            self._comp_view.refresh()
            self._show_scan_status(f"Battery #{result.battery_id} scanned in.", ok=True)

        elif result.action_taken == "wrong_battery":
            from ui.dialogs import WrongBatteryDialog
            err = result.error
            dlg = WrongBatteryDialog(result.battery_id, err.correct_battery_id, self)
            if dlg.exec() and dlg.override_accepted:
                self._open_beak_dialog(result.battery_id, override=True)

        elif result.action_taken == "already_on_field":
            self._handle_already_on_field(result.battery_id)

        elif result.action_taken in ("not_found", "invalid_id"):
            self._show_scan_status(f"Unknown battery ID: {raw_id}", ok=False)

        elif result.action_taken == "retired_battery":
            self._show_scan_status(f"Battery #{result.battery_id} is retired.", ok=False)

        elif result.action_taken in ("error", "unexpected_error"):
            err_msg = str(result.error) if result.error else "An unexpected error occurred."
            self._show_scan_status(f"Error: {err_msg}", ok=False)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Scan Error", err_msg)

        elif result.action_taken == "not_in_queue":
            self._show_scan_status(
                f"Battery #{result.battery_id} is not in the competition queue.", ok=False
            )

        # Cooling/Charging batteries accidentally scanned — silently ignore

    def _handle_already_on_field(self, battery_id: int) -> None:
        """
        In Practice mode, battery is already OnField (has an open session).
        Show a dialog so the operator chooses: Scan In (normal) or Reset Session Start (override).
        """
        from ui.dialogs import AlreadyOnFieldDialog
        dlg = AlreadyOnFieldDialog(battery_id, self)
        if not dlg.exec():
            return   # operator dismissed the dialog

        if dlg.choice == "scan_in":
            from app.services.session_service import scan_in_practice
            scan_in_practice(battery_id)
            self._home_view.refresh()
            self._show_scan_status(f"Battery #{battery_id} scanned in.", ok=True)

        elif dlg.choice == "reset_start":
            # Override: close old session and immediately ask for new beak readings → new session
            self._open_beak_dialog(battery_id, override=True)

    def _open_beak_dialog(self, battery_id: int, override: bool = False) -> None:
        """Collect beak readings from the operator, then scan the battery out."""
        from ui.dialogs import BeakReadingsDialog
        dlg = BeakReadingsDialog(battery_id, self)
        if dlg.exec():
            mode = AppState().mode
            if mode == AppMode.PRACTICE:
                from app.services.session_service import scan_out_practice
                scan_out_practice(battery_id, dlg.voltage, dlg.charge_pct, dlg.resistance_mohm)
                self._home_view.refresh()
                self._show_scan_status(f"Battery #{battery_id} scanned out.", ok=True)
            else:
                from app.services.session_service import scan_out_competition
                scan_out_competition(
                    battery_id, dlg.voltage, dlg.charge_pct, dlg.resistance_mohm,
                    override=override,
                )
                self._comp_view.refresh()
                self._show_scan_status(f"Battery #{battery_id} scanned out.", ok=True)

    def _show_scan_status(self, msg: str, ok: bool) -> None:
        """Display a brief scan result message in the status bar footer."""
        color = theme.GREEN if ok else theme.RED
        self._scan_status_label.setText(msg)
        self._scan_status_label.setStyleSheet(
            f"color: {color}; background: transparent;"
        )
        self._scan_status_timer.start()

    # -----------------------------------------------------------------------
    # Add battery flow
    # -----------------------------------------------------------------------

    def _show_add_battery_dialog(self) -> None:
        """Open the Add Battery dialog directly without requiring a PIN."""
        from ui.dialogs import AddBatteryDialog
        dlg = AddBatteryDialog(self)
        if dlg.exec():
            from app.services.battery_service import add_battery
            from datetime import date
            pd = date.fromisoformat(dlg.purchase_date) if dlg.purchase_date else None
            add_battery(dlg.brand, dlg.batch_number, dlg.broken_in, pd)
            self._home_view.refresh()

    def _on_edit_battery_requested(self, battery_id: int) -> None:
        """PIN-gated handler for editing a battery's brand/batch/purchase date."""
        from ui.dialogs import PinDialog, EditBatteryDialog
        pin_dlg = PinDialog(parent=self)
        if not pin_dlg.exec():
            return
        dlg = EditBatteryDialog(battery_id, self)
        if dlg.exec():
            from app.services.battery_service import update_battery
            from datetime import date
            pd = date.fromisoformat(dlg.purchase_date) if dlg.purchase_date else None
            update_battery(battery_id, dlg.brand, dlg.batch_number, pd)
            self._home_view.refresh()

    def _on_retire_battery_requested(self, battery_id: int) -> None:
        """PIN-gated handler for retiring a battery."""
        from ui.dialogs import PinDialog, ConfirmDialog
        confirm = ConfirmDialog(
            "RETIRE BATTERY",
            f"Retire Battery #{battery_id}?\n\nThe battery will be removed from the active fleet.\nAll history is retained.",
            "RETIRE",
            theme.RED,
            self,
        )
        if not confirm.exec():
            return
        pin_dlg = PinDialog(parent=self)
        if not pin_dlg.exec():
            return
        from app.services.battery_service import retire_battery
        retire_battery(battery_id)
        if AppState().is_competition:
            from app.services.competition_service import remove_from_competition_queue
            remove_from_competition_queue(battery_id)
            self._comp_view.refresh()
        self._home_view.refresh()
        self._show_scan_status(f"Battery #{battery_id} retired.", ok=True)

    # -----------------------------------------------------------------------
    # Competition view signal handlers
    # -----------------------------------------------------------------------

    def _on_add_battery_to_queue(self) -> None:
        """Show a picker for batteries not yet in the queue and add the selected ones."""
        from app.services.competition_service import get_batteries_not_in_queue, add_battery_to_competition
        from ui.dialogs import AddToQueueDialog
        available = get_batteries_not_in_queue()
        dlg = AddToQueueDialog(available, self)
        if dlg.exec() and dlg.selected_battery_ids:
            for battery_id in dlg.selected_battery_ids:
                add_battery_to_competition(battery_id)
            self._comp_view.refresh()

    def _confirm_end_competition(self) -> None:
        """Ask for confirmation and a PIN before ending the competition."""
        from ui.dialogs import PinDialog, ConfirmDialog
        confirm = ConfirmDialog(
            "END COMPETITION",
            "This will reset all batteries to Available and return to Practice Mode.",
            "END COMPETITION",
            theme.RED,
            self,
        )
        if confirm.exec():
            pin_dlg = PinDialog(parent=self)
            if pin_dlg.exec():
                from app.services.competition_service import end_competition
                end_competition()
                self._handle_competition_ended()

    def _set_battery_charging(self, battery_id: int) -> None:
        """Move a battery to Charging status (from Available, Cooling, or ReadyToCharge)."""
        from app.services.competition_service import set_battery_charging
        set_battery_charging(battery_id)
        self._comp_view.refresh()

    def _set_battery_available(self, battery_id: int) -> None:
        """Mark a Charging battery as Available — charging is done, ready to go out."""
        from app.services.competition_service import set_battery_available
        set_battery_available(battery_id)
        self._comp_view.refresh()

    def _on_cooling_complete(self, battery_id: int) -> None:
        """Notify the operator that a battery has finished cooling."""
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox(self)
        msg.setWindowTitle("Cooling Complete")
        msg.setText(
            f"Battery #{battery_id} has finished cooling.\n"
            f"Press 'Set to Charging' on its card."
        )
        msg.setStyleSheet(
            f"QMessageBox {{ background: {theme.BG2}; color: {theme.TEXT}; }}"
        )
        msg.exec()

    def _on_battery_missing(self, battery_id: int) -> None:
        """Mark a battery missing and notify the operator."""
        from app.services.competition_service import mark_missing
        mark_missing(battery_id)
        self._comp_view.refresh()

        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox(self)
        msg.setWindowTitle("Battery Missing!")
        msg.setText(
            f"Battery #{battery_id} has been on field for over 30 minutes "
            f"and is now marked MISSING."
        )
        msg.setStyleSheet(
            f"QMessageBox {{ background: {theme.BG2}; color: {theme.RED}; }}"
        )
        msg.exec()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_app() -> None:
    """Entry point — creates the QApplication and launches the main window."""
    import sys
    app = QApplication(sys.argv)
    app.setStyleSheet(theme.APP_STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
