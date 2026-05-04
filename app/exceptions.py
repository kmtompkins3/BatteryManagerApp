class BatteryTrackerError(Exception):
    """Base exception for all Battery Tracker errors."""


# ── Battery ───────────────────────────────────────────────────────────────────

class BatteryNotFoundError(BatteryTrackerError):
    def __init__(self, battery_id: int):
        super().__init__(f"Battery {battery_id} not found.")
        self.battery_id = battery_id


class BatteryAlreadyRetiredError(BatteryTrackerError):
    def __init__(self, battery_id: int):
        super().__init__(f"Battery {battery_id} is already retired.")
        self.battery_id = battery_id


class BatteryNotBrokenInError(BatteryTrackerError):
    def __init__(self):
        super().__init__("Battery must be marked as broken-in before it can be saved.")


# ── Session ───────────────────────────────────────────────────────────────────

class SessionAlreadyOpenError(BatteryTrackerError):
    """Battery is already OnField — scan-out was attempted again."""
    def __init__(self, battery_id: int, session_id: int):
        super().__init__(
            f"Battery {battery_id} already has an open session (id={session_id})."
        )
        self.battery_id = battery_id
        self.session_id = session_id


class NoOpenSessionError(BatteryTrackerError):
    """Scan-in attempted on a battery with no open session."""
    def __init__(self, battery_id: int):
        super().__init__(f"Battery {battery_id} has no open session to close.")
        self.battery_id = battery_id


# ── Competition ───────────────────────────────────────────────────────────────

class WrongBatteryError(BatteryTrackerError):
    """Scanned battery is not the front of the FIFO queue."""
    def __init__(self, scanned_id: int, correct_battery_id: int):
        super().__init__(
            f"Wrong battery scanned (id={scanned_id}). "
            f"Front of queue is battery {correct_battery_id}."
        )
        self.scanned_id = scanned_id
        self.correct_battery_id = correct_battery_id


class CompetitionNotActiveError(BatteryTrackerError):
    def __init__(self):
        super().__init__("Competition mode is not currently active.")


class QueueEmptyError(BatteryTrackerError):
    def __init__(self):
        super().__init__("Competition queue is empty or all batteries are Missing.")


# ── Admin / Auth ──────────────────────────────────────────────────────────────

class InvalidPinError(BatteryTrackerError):
    def __init__(self):
        super().__init__("Incorrect admin PIN.")


class PinNotSetError(BatteryTrackerError):
    def __init__(self):
        super().__init__("Admin PIN has not been set yet.")


# ── Export ────────────────────────────────────────────────────────────────────

class ExportError(BatteryTrackerError):
    pass
