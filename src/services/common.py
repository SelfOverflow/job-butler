"""Common service types, cancellation, and progress."""

from collections.abc import Callable

# Re-export progress types from ingestion.base
ProgressFn = Callable[[str, int, int, str], None]


def no_progress(stage: str, done: int, total: int, detail: str) -> None:
    pass


class CancelledError(Exception):
    """Raised when an in-flight background command has been cancelled."""


class CancelToken:
    """Thread-safe cooperative cancellation token checked between work units."""

    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def check(self) -> None:
        if self._cancelled:
            raise CancelledError("Operation was cancelled")

