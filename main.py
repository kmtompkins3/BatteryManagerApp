from db.schema import init_db
from db.settings_dal import get_setting
from app.state import AppState
from app.constants import AppMode


def bootstrap() -> None:
    init_db()
    saved_mode = get_setting("current_mode") or AppMode.PRACTICE.value
    AppState().mode = AppMode(saved_mode)


if __name__ == "__main__":
    bootstrap()
    from ui.main_window import run_app
    run_app()
