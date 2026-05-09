"""EventStore port: append + load events with optimistic concurrency.

The Postgres adapter (Phase 1b) implements this against a single `events` table
with `UNIQUE(stream_id, version)` for optimistic concurrency. The load path
returns raw stored events; callers fold them with their own evolver function.

When snapshots are added later, `load` will internally read the latest snapshot
and replay only the events after it; the contract returned to callers is
unchanged.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True)
class NewEvent:
    """A domain event being written to the store. Wrapped at the app-layer boundary."""

    event_type: str
    schema_version: int
    payload: dict[str, Any]
    correlation_id: UUID
    causation_id: UUID | None = None


@dataclass(frozen=True)
class StoredEvent:
    """A domain event read from the store. Carries store-assigned metadata."""

    stream_id: str
    version: int
    event_type: str
    schema_version: int
    payload: dict[str, Any]
    correlation_id: UUID
    causation_id: UUID | None
    occurred_at: datetime
    recorded_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])


class ConcurrencyError(Exception):
    """Raised when `expected_version` does not match the stream's current version."""

    def __init__(self, stream_id: str, expected: int, actual: int) -> None:
        super().__init__(
            f"Optimistic concurrency conflict on stream {stream_id!r}: "
            f"expected version {expected}, found {actual}"
        )
        self.stream_id = stream_id
        self.expected = expected
        self.actual = actual


class EventStore(Protocol):
    """Append and load events with optimistic concurrency."""

    async def load(self, stream_id: str) -> tuple[list[StoredEvent], int]:
        """Load all events for a stream in order.

        Returns `(events, current_version)`. Returns `([], 0)` if the stream
        does not exist. Callers fold events with their evolver function.
        """
        ...

    async def append(
        self,
        stream_id: str,
        expected_version: int,
        events: list[NewEvent],
    ) -> int:
        """Append events with optimistic concurrency.

        Returns the new current version after append. Raises
        `ConcurrencyError` if `expected_version` does not match the stream's
        current version at the moment of write.
        """
        ...
