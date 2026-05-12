"""In-memory `EventStore` for unit tests and the `test` app environment.

Mirrors the Postgres adapter's contract: same optimistic-concurrency
semantics, same global ordering by an in-memory monotonic position counter,
same per-stream version invariants, AND the same `event_id` UNIQUE
constraint (a duplicate `event_id` in any append raises ValueError so
test failures match what production would surface as a Postgres
UniqueViolationError). A `threading.Lock` guards the dict and the position
counter so the same instance can be safely shared across concurrent
tasks (we hold the lock only across pure in-memory work, never across
awaits).
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
        self._event_ids: set[UUID] = set()
        self._position = count(start=1)
        # Fake xid8: monotonic per append() call. All events in the same
        # batch share a transaction_id (mirrors Postgres semantics where
        # one transaction can emit N events). Starts at a non-zero value
        # so the bookmark sentinel ('0'::xid8 in production, 0 here)
        # compares strictly less than any real value.
        self._transaction_id = count(start=1)
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

        key = (stream_type, stream_id)
        with self._lock:
            existing = self._streams.get(key)
            actual = existing[-1].version if existing else 0
            if actual != expected_version:
                raise ConcurrencyError(
                    stream_type=stream_type,
                    stream_id=stream_id,
                    expected=expected_version,
                    actual=actual,
                )
            # Mirror Postgres's UNIQUE(event_id) constraint. Detect both
            # in-batch duplicates and collisions with already-stored ids
            # before mutating, so a partial batch never lands.
            new_ids = [e.event_id for e in events]
            if len(set(new_ids)) != len(new_ids):
                msg = "Duplicate event_id within a single append batch"
                raise ValueError(msg)
            collisions = self._event_ids.intersection(new_ids)
            if collisions:
                msg = f"event_id already exists: {sorted(str(i) for i in collisions)}"
                raise ValueError(msg)
            if existing is None:
                existing = []
                self._streams[key] = existing
            now = datetime.now(tz=UTC)
            tx_id = next(self._transaction_id)
            next_version = expected_version
            for event in events:
                next_version += 1
                stored = StoredEvent(
                    position=next(self._position),
                    event_id=event.event_id,
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
                    transaction_id=tx_id,
                )
                existing.append(stored)
                self._event_ids.add(event.event_id)
            return next_version
