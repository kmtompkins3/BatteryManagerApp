# STR Brand colors and shared style helpers for the FRC Battery Manager UI.
# All UI files import from here — never hardcode hex color strings elsewhere.

from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import QPushButton

# Background layers
BG           = '#0A0A0B'   # main window background
BG2          = '#121214'   # panel / card surface
BG3          = '#1A1A1D'   # elevated surface, hover state

# Borders
BORDER       = '#26262B'   # subtle separator
BORDER2      = '#34343A'   # stronger border

# Text
TEXT         = '#F5F5F5'   # primary text
TEXT_DIM     = '#8A8A92'   # secondary / label text
TEXT_FAINT   = '#5A5A62'   # placeholder / disabled text

# STR Brand accent colors
ORANGE       = '#FF4200'   # primary accent, OnField status
RED          = '#DC0000'   # danger accent, Missing status
PURPLE       = '#4600AA'   # Charging status

# Semantic status colors
GREEN        = '#22C55E'   # Available
BLUE         = '#3B9EFF'   # Cooling
GRAY         = '#6A6A72'   # Retired

# Maps BatteryStatus.value strings to their display colors
STATUS_COLORS: dict[str, str] = {
    'Available': GREEN,
    'OnField':   ORANGE,
    'Cooling':   BLUE,
    'Charging':  PURPLE,
    'Missing':   RED,
    'Retired':   GRAY,
}

# Primary font. Falls back to Courier New if Space Mono is not installed.
FONT_FAMILY  = 'Space Mono'


def get_font(bold: bool = False, size: int = 11) -> QFont:
    """Return a Space Mono QFont at the given size and weight."""
    font = QFont(FONT_FAMILY, size)
    font.setBold(bold)
    font.setStyleHint(QFont.StyleHint.Monospace)
    return font


def status_color(status: str) -> str:
    """Return the hex color string for a battery status value."""
    return STATUS_COLORS.get(status, TEXT_DIM)


def make_primary_button(label: str, color: str = ORANGE) -> QPushButton:
    """Return a filled STR-branded action button."""
    btn = QPushButton(label)
    btn.setFont(get_font(bold=True, size=10))
    hover = _lighten(color)
    btn.setStyleSheet(f"""
        QPushButton {{
            background: {color};
            color: #ffffff;
            border: none;
            padding: 9px 16px;
        }}
        QPushButton:hover {{ background: {hover}; }}
        QPushButton:disabled {{ background: {BG3}; color: {TEXT_FAINT}; }}
    """)
    return btn


def make_ghost_button(label: str) -> QPushButton:
    """Return a bordered ghost/cancel button."""
    btn = QPushButton(label)
    btn.setFont(get_font(bold=True, size=10))
    btn.setStyleSheet(f"""
        QPushButton {{
            background: transparent;
            color: {TEXT};
            border: 1px solid {BORDER2};
            padding: 9px 16px;
        }}
        QPushButton:hover {{ background: {BG3}; }}
    """)
    return btn


def make_danger_button(label: str) -> QPushButton:
    """Return a bordered danger (red) button."""
    btn = QPushButton(label)
    btn.setFont(get_font(bold=True, size=10))
    btn.setStyleSheet(f"""
        QPushButton {{
            background: transparent;
            color: {RED};
            border: 1px solid {RED};
            padding: 9px 16px;
        }}
        QPushButton:hover {{ background: rgba(220,0,0,0.12); }}
    """)
    return btn


def _lighten(hex_color: str) -> str:
    """Return a slightly lighter version of a hex color for hover states."""
    c = QColor(hex_color)
    h, s, v, a = c.getHsvF()
    c.setHsvF(h, max(0.0, s - 0.05), min(1.0, v + 0.12), a)
    return c.name()


# Full QSS stylesheet applied to QApplication at startup.
APP_STYLESHEET = f"""
    QMainWindow, QWidget {{
        background-color: {BG};
        color: {TEXT};
        font-family: "{FONT_FAMILY}", "Courier New", monospace;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER};
        border: 2px solid {BG};
        border-radius: 4px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {BORDER2}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 10px;
        margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background: {BORDER};
        border: 2px solid {BG};
        border-radius: 4px;
        min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {BORDER2}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    QTableWidget {{
        background-color: {BG};
        gridline-color: {BORDER};
        border: none;
        outline: 0;
    }}
    QTableWidget::item {{
        padding: 8px 12px;
        border: none;
    }}
    QTableWidget::item:selected {{
        background-color: rgba(255,66,0,0.15);
        color: {TEXT};
    }}
    QHeaderView::section {{
        background-color: {BG};
        color: {TEXT_DIM};
        padding: 10px 12px;
        border: none;
        border-bottom: 1px solid {BORDER};
        font-weight: bold;
        font-size: 10px;
    }}
    QLineEdit, QComboBox {{
        background-color: {BG};
        color: {TEXT};
        border: 1px solid {BORDER2};
        padding: 8px 10px;
        font-family: "{FONT_FAMILY}", "Courier New", monospace;
        font-size: 13px;
        selection-background-color: {ORANGE};
    }}
    QLineEdit:focus {{ border: 1px solid {ORANGE}; }}
    QComboBox:focus {{ border: 1px solid {ORANGE}; }}
    QComboBox::drop-down {{ border: none; width: 24px; }}
    QComboBox QAbstractItemView {{
        background-color: {BG2};
        color: {TEXT};
        border: 1px solid {BORDER2};
        selection-background-color: {BG3};
    }}
    QToolTip {{
        background-color: {BG3};
        color: {TEXT};
        border: 1px solid {BORDER2};
        padding: 6px;
    }}
    QDialog {{
        background-color: {BG2};
        border: 1px solid {BORDER2};
    }}
    QCheckBox {{
        color: {TEXT};
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {BORDER2};
        background: {BG};
    }}
    QCheckBox::indicator:checked {{
        background: {PURPLE};
        border: 1px solid {PURPLE};
    }}
    QLabel {{
        color: {TEXT};
    }}
    QSplitter::handle {{
        background: {BORDER};
    }}
"""
