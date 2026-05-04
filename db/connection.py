import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

DB_PATH: Path = Path(__file__).parent.parent / "battery_tracker.db"


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """
    Yields an open SQLite connection with WAL journal mode and
    row_factory set so rows behave like dicts (sqlite3.Row).
    Auto-commits on clean exit, rolls back on exception.
    """
    conn = sqlite3.connect(str(DB_PATH), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
