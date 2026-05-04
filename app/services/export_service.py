from __future__ import annotations

import csv
import io
from datetime import datetime
from pathlib import Path

import qrcode
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import db.session_dal as _session_dal
import db.beak_dal as _beak_dal
import db.battery_dal as _bat_dal
from app.exceptions import BatteryNotFoundError, ExportError

EXPORTS_DIR: Path = Path(__file__).parent.parent.parent / "exports"
ASSETS_DIR: Path  = Path(__file__).parent.parent.parent / "assets"

_FONT_BOLD = "SpaceMonoBold"
_FONT_BOOK = "SpaceMonoBook"
_fonts_registered = False


def _ensure_exports_dir() -> None:
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _register_fonts() -> None:
    global _fonts_registered
    if _fonts_registered:
        return
    bold_path = ASSETS_DIR / "SpaceMono-Bold.ttf"
    book_path = ASSETS_DIR / "SpaceMono-Regular.ttf"
    registered_any = False
    if bold_path.exists():
        pdfmetrics.registerFont(TTFont(_FONT_BOLD, str(bold_path)))
        registered_any = True
    if book_path.exists():
        pdfmetrics.registerFont(TTFont(_FONT_BOOK, str(book_path)))
        registered_any = True
    _fonts_registered = registered_any


def generate_qr_pdf(battery_id: int) -> Path:
    """
    Generates a single-page PDF label for the given battery.
    - QR encodes the Battery ID as a plain integer string.
    - Battery ID is printed below the QR in Space Mono Bold.
    - Saves to exports/battery_{id}_label.pdf and returns the Path.
    Raises BatteryNotFoundError if battery does not exist.
    Raises ExportError on any other failure.
    """
    battery = _bat_dal.get_battery(battery_id)
    if battery is None:
        raise BatteryNotFoundError(battery_id)

    try:
        _ensure_exports_dir()
        _register_fonts()

        # Generate QR image
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(str(battery_id))
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        # Save QR to an in-memory buffer
        img_buffer = io.BytesIO()
        img.save(img_buffer, format="PNG")
        img_buffer.seek(0)

        # Build PDF
        out_path = EXPORTS_DIR / f"battery_{battery_id}_label.pdf"
        page_w, page_h = LETTER
        qr_size = 4 * inch
        qr_x = (page_w - qr_size) / 2
        qr_y = (page_h - qr_size) / 2 + 0.5 * inch

        c = rl_canvas.Canvas(str(out_path), pagesize=LETTER)

        # Draw QR image (ImageReader wraps the BytesIO so reportlab accepts it)
        c.drawImage(
            ImageReader(img_buffer),
            x=qr_x,
            y=qr_y,
            width=qr_size,
            height=qr_size,
        )

        # Draw Battery ID label below QR; fall back to built-in font if Space Mono not bundled
        bold_available = (ASSETS_DIR / "SpaceMono-Bold.ttf").exists()
        font = _FONT_BOLD if bold_available else "Helvetica-Bold"
        c.setFont(font, 24)
        label_y = qr_y - 0.5 * inch
        c.drawCentredString(page_w / 2, label_y, str(battery_id))

        c.save()
        return out_path

    except (BatteryNotFoundError, ExportError):
        raise
    except Exception as exc:
        raise ExportError(f"Failed to generate QR PDF for battery {battery_id}: {exc}") from exc


def export_battery_history_csv(battery_id: int) -> Path:
    """
    Exports the full session/reading history for a battery to a CSV file.
    - Filename: exports/battery_{id}_history_{YYYYMMDD}.csv
    - Columns: date_time, duration_minutes, voltage, charge_pct, resistance_mohm
    - If override_used=True on a session, all data columns show 'Override'.
    Raises BatteryNotFoundError if battery does not exist.
    Raises ExportError on any other failure.
    """
    battery = _bat_dal.get_battery(battery_id)
    if battery is None:
        raise BatteryNotFoundError(battery_id)

    try:
        _ensure_exports_dir()

        sessions = _session_dal.get_sessions_for_battery(battery_id)
        readings_by_session = {
            r.session_id: r
            for r in _beak_dal.get_readings_for_battery(battery_id)
        }

        date_str = datetime.now().strftime("%Y%m%d")
        out_path = EXPORTS_DIR / f"battery_{battery_id}_history_{date_str}.csv"

        fieldnames = ["date_time", "duration_minutes", "voltage", "charge_pct", "resistance_mohm"]

        with out_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for session in sessions:
                reading = readings_by_session.get(session.session_id)
                if session.override_used:
                    writer.writerow({
                        "date_time":         "Override",
                        "duration_minutes":  "Override",
                        "voltage":           "Override",
                        "charge_pct":        "Override",
                        "resistance_mohm":   "Override",
                    })
                else:
                    writer.writerow({
                        "date_time": (
                            session.scan_out_time.isoformat() if session.scan_out_time else ""
                        ),
                        "duration_minutes": (
                            round(session.duration_minutes, 2)
                            if session.duration_minutes is not None
                            else ""
                        ),
                        "voltage":         round(reading.voltage, 2)         if reading else "",
                        "charge_pct":      reading.charge_pct                 if reading else "",
                        "resistance_mohm": reading.resistance_mohm            if reading else "",
                    })

        return out_path

    except (BatteryNotFoundError, ExportError):
        raise
    except Exception as exc:
        raise ExportError(f"Failed to export CSV for battery {battery_id}: {exc}") from exc
