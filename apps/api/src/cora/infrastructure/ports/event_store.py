"""EventStore port: append + load events with optimistic concurrency.

The Postgres adapter (Phase 1b) implements this against a single `events` table
with `UNIQUE(stream_type, stream_id, version)` for optimistic concurrency. The
load path returns raw stored events; callers fold them with their own evolver
function.

When snapshots are added later, `load` will internally read the latest snapshot
and replay only the events after it; the contract returned to callers is
unchanged.

Sequence-rollback hazard for projections (read this before building one)
-----------------------------------------------------------------------
`StoredEvent.position` is a global commit-order watermark from a Postgres
`bigserial`. Sequences advance even on rolled-back transactions, and a
later-started transaction can commit before an earlier one. A naive projection
that polls `WHERE position > last_processed_position` will skip events from a
slow transaction that committed after a fast one with a higher position.

Mitigations the projection adapter must apply:
  - Track `last_processed_position` per projection.
  - When polling, exclude positions whose owning transactions are still
    in-flight (e.g. via `pg_snapshot_xmin(pg_current_snapshot())`), or
    re-scan a small overlap window each tick to recover any late commits.
  - Combined with the LISTEN/NOTIFY wake-up signal, polling can be infrequent.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True)
class NewEvent:
    """A domain event being written to the store. Wrapped at the app-layer boundary.

    `event_id` is the per-event stable identity (UUIDv7 in production via
    the IdGenerator port). It's the unit of downstream deduplication for
    at-least-once delivery to projections, and the natural value to use as
    the next command's `causation_id` in saga / process-manager chains.
    Generated in the handler (one per emitted event) so the decider stays
    pure and the to_new_event factory stays a dict-shuffle.

    `occurred_at` is domain time, set by the handler via the Clock port. The
    store also records its own `recorded_at` (DB write time) on persistence.
    """

    event_id: UUID
    event_type: str
    schema_version: int
    payload: dict[str, Any]
    occurred_at: datetime
    correlation_id: UUID
    causation_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass(frozen=True)
class StoredEvent:
    """A domain event read from the store. Carries store-assigned metadata.

    `position` is the global commit-order watermark (`bigserial` from the DB).
    See module docstring for the sequence-rollback hazard projections must
    handle when consuming events by position.

    `event_id` is the producer-assigned identity (the same UUID supplied
    at append time in NewEvent.event_id). It is UNIQUE across the events
    table and serves as the dedup key for downstream consumers.
    """

    position: int
    event_id: UUID
    stream_type: str
    stream_id: UUID
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

    def __init__(
        self,
        stream_type: str,
        stream_id: UUID,
        expected: int,
        actual: int,
    ) -> None:
        super().__init__(
            f"Optimistic concurrency conflict on stream "
            f"{stream_type}/{stream_id}: expected version {expected}, "
            f"found {actual}"
        )
        self.stream_type = stream_type
        self.stream_id = stream_id
        self.expected = expected
        self.actual = actual


class EventStore(Protocol):
    """Append and load events with optimistic concurrency."""

    async def load(
        self,
        stream_type: str,
        stream_id: UUID,
    ) -> tuple[list[StoredEvent], int]:
        """Load all events for a stream in order.

        Returns `(events, current_version)`. Returns `([], 0)` if the stream
        does not exist. Callers fold events with their evolver function.
        """
        ...

    async def append(
        self,
        stream_type: str,
        stream_id: UUID,
        expected_version: int,
        events: list[NewEvent],
    ) -> int:
        """Append events with optimistic concurrency.

        Returns the new current version after append. Raises
        `ConcurrencyError` if `expected_version` does not match the stream's
        current version at the moment of write.
        """
        ...
