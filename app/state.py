from threading import Lock
from app.constants import AppMode


class AppState:
    """
    Thread-safe singleton. Holds transient in-memory state only.
    Durable state (queue, timers, mode) lives in SQLite and is
    loaded from AppSettings on bootstrap.
    """

    _instance: "AppState | None" = None
    _lock: Lock = Lock()

    def __new__(cls) -> "AppState":
        with cls._lock:
            if cls._instance is None:
                inst = super().__new__(cls)
                inst._mode = AppMode.PRACTICE
                cls._instance = inst
        return cls._instance

    @property
    def mode(self) -> AppMode:
        return self._mode

    @mode.setter
    def mode(self, value: AppMode) -> None:
        self._mode = value

    @property
    def is_competition(self) -> bool:
        return self._mode == AppMode.COMPETITION

    @property
    def is_practice(self) -> bool:
        return self._mode == AppMode.PRACTICE

    def reset(self) -> None:
        """Drop back to Practice mode. Call after ending a competition."""
        self._mode = AppMode.PRACTICE
