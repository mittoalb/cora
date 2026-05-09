"""In-memory `EventStore` for unit tests and the `test` app environment.

Mirrors the Postgres adapter's contract: same optimistic-concurrency
semantics, same global ordering by an in-memory monotonic position counter,
same per-stream version invariants. Not thread-safe; tests are single-task.
"""

from copy import deepcopy
from datetime import UTC, datetime
from itertools import count
from threading import Lock
from uuid import UUID

from cora.infrastructure.ports.event_store import (
    ConcurrencyError,
    NewEvent,
    StoredEvent,
)


class InMemoryEventStore:
    """Thread-safe in-memory implementation of the EventStore port."""

    def __init__(self) -> None:
        self._streams: dict[tuple[str, UUID], list[StoredEvent]] = {}
        self._position = count(start=1)
        self._lock = Lock()

    async def load(
        self,
        stream_type: str,
        stream_id: UUID,
    ) -> tuple[list[StoredEvent], int]:
        with self._lock:
            events = list(self._streams.get((stream_type, stream_id), []))
        version = events[-1].version if events else 0
        return events, version

    async def append(
        self,
        stream_type: str,
        stream_id: UUID,
        expected_version: int,
        events: list[NewEvent],
    ) -> int:
        if not events:
            return expected_version

        with self._lock:
            existing = self._streams.setdefault((stream_type, stream_id), [])
            actual = existing[-1].version if existing else 0
            if actual != expected_version:
                raise ConcurrencyError(
                    stream_type=stream_type,
                    stream_id=stream_id,
                    expected=expected_version,
                    actual=actual,
                )
            now = datetime.now(tz=UTC)
            next_version = expected_version
            for event in events:
                next_version += 1
                stored = StoredEvent(
                    position=next(self._position),
                    stream_type=stream_type,
                    stream_id=stream_id,
                    version=next_version,
                    event_type=event.event_type,
                    schema_version=event.schema_version,
                    payload=deepcopy(event.payload),
                    metadata=deepcopy(event.metadata),
                    correlation_id=event.correlation_id,
                    causation_id=event.causation_id,
                    occurred_at=event.occurred_at,
                    recorded_at=now,
                )
                existing.append(stored)
            return next_version
