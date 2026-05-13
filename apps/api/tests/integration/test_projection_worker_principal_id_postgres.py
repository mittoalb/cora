"""End-to-end: the projection worker delivers `principal_id` to
subscribers (Phase 9b-a cleanup).

The Phase 9b-a infra commit (3839c1f) wired `principal_id` through
the events table + ports + adapters + envelope helper, but the
projection worker has its own `_ADVANCE_SQL` SELECT that mirrors
(rather than imports from) the postgres event-store adapter. The
worker's SELECT was missed in the original commit, which would
silently deliver `principal_id=None` to every subscriber even when
the underlying row had a real value, defeating the whole purpose
of the day-1 hook.

This test pins the end-to-end round trip:

  1. Append an event directly to the events table with a
     non-NULL principal_id (bypassing handlers, which don't yet
     thread the kwarg until 9b-b).
  2. Drain a custom test-only Projection subscribed to the event
     type. The projection captures the StoredEvent it receives.
  3. Assert the captured event's principal_id matches what was
     written.

Without the worker SELECT fix, the assertion would fail with
`captured.principal_id is None`. Catches future regression of
the same shape (worker SELECT drifting from event-store adapter
SELECT when a new envelope field is added).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.ports.event_store import NewEvent, StoredEvent
from cora.infrastructure.postgres.event_store import PostgresEventStore
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.infrastructure.projection.handler import ConnectionLike


class _CapturingProjection:
    """Test-only projection that captures every StoredEvent it receives.

    Subscribes to the synthetic `Phase9bAEvent` event type so it
    only sees the events this test writes. apply() is no-op-
    idempotent (just appends to a list) so the worker's at-least-
    once guarantee doesn't matter for the assertion.
    """

    name = "proj_test_phase_9b_a_capture"
    subscribed_event_types = frozenset({"Phase9bAEvent"})

    def __init__(self) -> None:
        self.captured: list[StoredEvent] = []

    async def apply(
        self,
        event: StoredEvent,
        conn: ConnectionLike,
    ) -> None:
        _ = conn
        self.captured.append(event)


async def _ensure_bookmark(db_pool: asyncpg.Pool, name: str) -> None:
    """Insert a bookmark row for the test projection so the worker
    has a starting point. Mirrors what a real projection's migration
    would do via `INSERT INTO projection_bookmarks (name) VALUES (...)`.
    """
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO projection_bookmarks (name) VALUES ($1) ON CONFLICT DO NOTHING",
            name,
        )


@pytest.mark.integration
async def test_worker_delivers_non_null_principal_id_to_subscriber(
    db_pool: asyncpg.Pool,
) -> None:
    """The load-bearing test for the worker SELECT fix.

    Without the cleanup, this assertion fails because the worker's
    `_ADVANCE_SQL` doesn't include `principal_id` in its SELECT
    column list, so `_row_to_stored_event` reads None regardless
    of the column value.
    """
    projection = _CapturingProjection()
    await _ensure_bookmark(db_pool, projection.name)

    store = PostgresEventStore(db_pool)
    stream_id = uuid4()
    principal = UUID("01900000-0000-7000-8000-00000000bb22")
    await store.append(
        "TestStream",
        stream_id,
        0,
        [
            NewEvent(
                event_id=uuid4(),
                event_type="Phase9bAEvent",
                schema_version=1,
                payload={"k": "v"},
                occurred_at=datetime.now(tz=UTC),
                correlation_id=uuid4(),
                causation_id=None,
                metadata={},
                principal_id=principal,
            )
        ],
    )

    registry = ProjectionRegistry()
    registry.register(projection)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)

    assert len(projection.captured) == 1, (
        f"Expected 1 captured event, got {len(projection.captured)}. "
        f"The worker may not be delivering subscribed events at all."
    )
    assert projection.captured[0].principal_id == principal, (
        f"Worker delivered principal_id={projection.captured[0].principal_id!r}, "
        f"expected {principal!r}. The worker's _ADVANCE_SQL SELECT or "
        f"_row_to_stored_event likely doesn't pull the column."
    )


@pytest.mark.integration
async def test_worker_delivers_null_principal_id_to_subscriber(
    db_pool: asyncpg.Pool,
) -> None:
    """Sanity: the NULL case round-trips too. Pre-hook events
    legitimately have NULL principal_id; subscribers should see
    Python None, not crash on the row read."""
    projection = _CapturingProjection()
    await _ensure_bookmark(db_pool, projection.name)

    store = PostgresEventStore(db_pool)
    stream_id = uuid4()
    await store.append(
        "TestStream",
        stream_id,
        0,
        [
            NewEvent(
                event_id=uuid4(),
                event_type="Phase9bAEvent",
                schema_version=1,
                payload={"k": "v"},
                occurred_at=datetime.now(tz=UTC),
                correlation_id=uuid4(),
                causation_id=None,
                metadata={},
                principal_id=None,
            )
        ],
    )

    registry = ProjectionRegistry()
    registry.register(projection)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)

    assert len(projection.captured) == 1
    assert projection.captured[0].principal_id is None
