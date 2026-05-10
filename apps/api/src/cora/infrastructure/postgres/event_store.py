"""Postgres-backed `EventStore` adapter.

Optimistic concurrency is enforced by the `events_stream_version_unique`
UNIQUE constraint on `(stream_type, stream_id, version)`. On conflict the
adapter reads the current version and raises `ConcurrencyError` so the
caller can retry with a fresh load.

The `events_event_id_unique` UNIQUE INDEX on `event_id` is a separate
constraint that producers should never violate (UUIDv7 collisions are
astronomically unlikely; a violation indicates a wrapper that's reusing
an id from a cached generator). The adapter inspects the violated
constraint name and re-raises the original `UniqueViolationError`
unchanged for that case so the bug surfaces loudly rather than being
mis-mapped to ConcurrencyError.

Append is wrapped in a single transaction so partial writes never appear
to readers. The AFTER INSERT trigger fires `pg_notify` per row (see
migration `20260509120000_init_events.sql`); listeners use that as a
wake-up signal and always poll from a persisted watermark to recover any
missed notifications.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# asyncpg's stubs are loose; suppress only at module level for the
# adapter file. The port + StoredEvent fields keep typing strict for
# every caller above the boundary.

from typing import Any
from uuid import UUID

import asyncpg

from cora.infrastructure.ports.event_store import (
    ConcurrencyError,
    NewEvent,
    StoredEvent,
)

_LOAD_SQL = """
SELECT position, event_id, stream_type, stream_id, version, event_type,
       schema_version, payload, metadata, correlation_id, causation_id,
       occurred_at, recorded_at
FROM events
WHERE stream_type = $1 AND stream_id = $2
ORDER BY version
"""

_APPEND_SQL = """
INSERT INTO events (
    event_id, stream_type, stream_id, version, event_type, schema_version,
    payload, metadata, correlation_id, causation_id, occurred_at
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
"""

_CURRENT_VERSION_SQL = """
SELECT COALESCE(MAX(version), 0) FROM events
WHERE stream_type = $1 AND stream_id = $2
"""

_STREAM_VERSION_CONSTRAINT = "events_stream_version_unique"


class PostgresEventStore:
    """asyncpg-backed `EventStore` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def load(
        self,
        stream_type: str,
        stream_id: UUID,
    ) -> tuple[list[StoredEvent], int]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_LOAD_SQL, stream_type, stream_id)
        events = [_row_to_event(row) for row in rows]
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

        try:
            async with self._pool.acquire() as conn, conn.transaction():
                next_version = expected_version
                for event in events:
                    next_version += 1
                    await conn.execute(
                        _APPEND_SQL,
                        event.event_id,
                        stream_type,
                        stream_id,
                        next_version,
                        event.event_type,
                        event.schema_version,
                        event.payload,
                        event.metadata,
                        event.correlation_id,
                        event.causation_id,
                        event.occurred_at,
                    )
                return next_version
        except asyncpg.UniqueViolationError as exc:
            # The events table has two unique constraints. Map the
            # stream-version one to ConcurrencyError (expected, retry-able);
            # any other one (today: events_event_id_unique) is a producer
            # bug — re-raise unchanged so it surfaces loudly.
            if getattr(exc, "constraint_name", None) != _STREAM_VERSION_CONSTRAINT:
                raise
            # Transaction is rolled back; read the actual version on a fresh
            # connection so the caller can decide whether to retry.
            async with self._pool.acquire() as fresh:
                actual = await fresh.fetchval(_CURRENT_VERSION_SQL, stream_type, stream_id)
            raise ConcurrencyError(
                stream_type=stream_type,
                stream_id=stream_id,
                expected=expected_version,
                actual=int(actual or 0),
            ) from exc


def _row_to_event(row: Any) -> StoredEvent:
    payload: dict[str, Any] = row["payload"]
    metadata: dict[str, Any] = row["metadata"]
    return StoredEvent(
        position=int(row["position"]),
        event_id=row["event_id"],
        stream_type=str(row["stream_type"]),
        stream_id=row["stream_id"],
        version=int(row["version"]),
        event_type=str(row["event_type"]),
        schema_version=int(row["schema_version"]),
        payload=payload,
        metadata=metadata,
        correlation_id=row["correlation_id"],
        causation_id=row["causation_id"],
        occurred_at=row["occurred_at"],
        recorded_at=row["recorded_at"],
    )
