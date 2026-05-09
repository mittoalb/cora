"""Clock port: testable abstraction over wall-clock time."""

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Returns the current time. Implementations may be system-backed or frozen."""

    def now(self) -> datetime: ...


class SystemClock:
    """Production adapter: wraps `datetime.now(tz=UTC)`."""

    def now(self) -> datetime:
        return datetime.now(tz=UTC)


class FrozenClock:
    """Test adapter: returns a fixed time. Mutate via `set` if needed."""

    def __init__(self, frozen_at: datetime) -> None:
        self._frozen_at = frozen_at

    def now(self) -> datetime:
        return self._frozen_at

    def set(self, frozen_at: datetime) -> None:
        self._frozen_at = frozen_at
