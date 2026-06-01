"""Domain errors used by measurement runners and instruments."""


class MeasurementError(Exception):
    """Base error for measurement failures."""


class SafetyLimitError(MeasurementError):
    """Raised when a software or instrument safety limit is reached."""

    def __init__(self, message: str, triggered_limit: str):
        super().__init__(message)
        self.triggered_limit = triggered_limit
