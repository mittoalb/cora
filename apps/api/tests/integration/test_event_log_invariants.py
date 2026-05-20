"""Event-log structural invariants.

Asserts properties the adapter and aggregate evolvers depend on but
the `events` table schema alone does not enforce. Complements:

- `events_stream_version_unique` (UNIQUE per-stream version) — enforced
- `events_event_id_unique` (UNIQUE event_id) — enforced
- `position` `bigserial` PK (monotonic global allocation) — enforced
- REVOKE UPDATE/DELETE on `events` for `cora_app` — covered by
  `test_migration_revokes.py` (declarative) and
  `test_cora_app_role_revoke_postgres.py` (runtime).

What this file adds, that the DB does not enforce:

1. Per-stream `version` is contiguous starting at 1 — evolvers fold
   `[1..N]` and break on holes; UNIQUE allows `{1, 3, 7}`.
2. Per-stream `recorded_at` is non-decreasing with `version` — append
   order should match wall-clock order within a stream.
3. `occurred_at` not wildly ahead of `recorded_at` (5s tolerance) —
   catches corrupted timestamps and swapped fields while tolerating
   host/container clock skew. The two columns come from different
   clocks (handler wall-clock vs PG `now()`), so strict ordering is
   not actually guaranteed.
4. `causation_id`, when set, references an `event_id` that exists —
   no FK enforces this (causation may cross aggregates/streams).

Each test populates its own fixture data via `PostgresEventStore`, so
this also exercises the adapter end-to-end. Tests are integration tier
because the invariants are about real PG state, not source-tree shape.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.ports.event_store import NewEvent
from cora.infrastructure.postgres.event_store import PostgresEventStore


def _make_event(
    *,
    event_id: UUID | None = None,
    causation_id: UUID | None = None,
    occurred_at: datetime | None = None,
) -> NewEvent:
    return NewEvent(
        event_id=event_id if event_id is not None else uuid4(),
        event_type="InvariantTest",
        schema_version=1,
        payload={},
        occurred_at=occurred_at if occurred_at is not None else datetime.now(tz=UTC),
        correlation_id=uuid4(),
        causation_id=causation_id,
        metadata={},
        principal_id=uuid4(),
    )


@pytest.mark.integration
async def test_empty_store_satisfies_all_invariants(db_pool: asyncpg.Pool) -> None:
    """All invariant queries return empty / pass against a fresh store."""
    async with db_pool.acquire() as conn:
        gaps = await conn.fetch(_GAP_QUERY)
        non_unit_starts = await conn.fetch(_NON_UNIT_START_QUERY)
        time_inversions = await conn.fetch(_TIME_INVERSION_QUERY)
        recorded_inversions = await conn.fetch(_RECORDED_INVERSION_QUERY)
        orphan_causations = await conn.fetch(_ORPHAN_CAUSATION_QUERY)

    assert gaps == []
    assert non_unit_starts == []
    assert time_inversions == []
    assert recorded_inversions == []
    assert orphan_causations == []


@pytest.mark.integration
async def test_per_stream_version_is_contiguous_starting_at_1(
    db_pool: asyncpg.Pool,
) -> None:
    """Every stream's versions form `[1, 2, ..., N]` with no holes."""
    store = PostgresEventStore(db_pool)
    for stream_id, count in [(uuid4(), 1), (uuid4(), 3), (uuid4(), 5)]:
        await store.append("InvariantStream", stream_id, 0, [_make_event() for _ in range(count)])

    async with db_pool.acquire() as conn:
        gaps = await conn.fetch(_GAP_QUERY)
        non_unit_starts = await conn.fetch(_NON_UNIT_START_QUERY)

    assert gaps == [], (
        f"streams with non-contiguous version sequences: "
        f"{[(r['stream_type'], r['stream_id'], r['versions']) for r in gaps]}"
    )
    assert non_unit_starts == [], (
        f"streams whose first version != 1: "
        f"{[(r['stream_type'], r['stream_id'], r['min_version']) for r in non_unit_starts]}"
    )


@pytest.mark.integration
async def test_per_stream_recorded_at_is_non_decreasing_with_version(
    db_pool: asyncpg.Pool,
) -> None:
    """Within a stream, `recorded_at` does not go backwards as `version` grows."""
    store = PostgresEventStore(db_pool)
    stream_id = uuid4()
    for _ in range(5):
        await store.append(
            "InvariantStream",
            stream_id,
            (await store.load("InvariantStream", stream_id))[1],
            [_make_event()],
        )

    async with db_pool.acquire() as conn:
        inversions = await conn.fetch(_RECORDED_INVERSION_QUERY)

    assert inversions == [], (
        f"streams with recorded_at decreasing across versions: "
        f"{[(r['stream_type'], r['stream_id'], r['v1'], r['v2']) for r in inversions]}"
    )


@pytest.mark.integration
async def test_occurred_at_not_wildly_ahead_of_recorded_at(
    db_pool: asyncpg.Pool,
) -> None:
    """`occurred_at` and `recorded_at` are sampled from independent clocks
    (handler wall-clock vs PG `now()`), so strict ordering isn't a real
    invariant — but a 5-second gap signals corruption, not skew.
    """
    store = PostgresEventStore(db_pool)
    await store.append("InvariantStream", uuid4(), 0, [_make_event() for _ in range(3)])

    async with db_pool.acquire() as conn:
        inversions = await conn.fetch(_TIME_INVERSION_QUERY)

    assert inversions == [], (
        f"events with occurred_at > recorded_at + 5s (corruption, not skew): "
        f"{[(r['event_id'], r['occurred_at'], r['recorded_at']) for r in inversions]}"
    )


@pytest.mark.integration
async def test_causation_id_when_set_references_an_existing_event(
    db_pool: asyncpg.Pool,
) -> None:
    """No event has a `causation_id` pointing to a missing `event_id`."""
    store = PostgresEventStore(db_pool)
    cause_id = uuid4()
    await store.append("InvariantStream", uuid4(), 0, [_make_event(event_id=cause_id)])
    await store.append("InvariantStream", uuid4(), 0, [_make_event(causation_id=cause_id)])

    async with db_pool.acquire() as conn:
        orphans = await conn.fetch(_ORPHAN_CAUSATION_QUERY)

    assert orphans == [], (
        f"events whose causation_id points to a non-existent event_id: "
        f"{[(r['event_id'], r['causation_id']) for r in orphans]}"
    )


_GAP_QUERY = """
SELECT stream_type, stream_id, array_agg(version ORDER BY version) AS versions
FROM events
GROUP BY stream_type, stream_id
HAVING max(version) <> count(*) OR min(version) <> 1
"""

_NON_UNIT_START_QUERY = """
SELECT stream_type, stream_id, min(version) AS min_version
FROM events
GROUP BY stream_type, stream_id
HAVING min(version) <> 1
"""

_RECORDED_INVERSION_QUERY = """
WITH ordered AS (
    SELECT
        stream_type,
        stream_id,
        version,
        recorded_at,
        lag(recorded_at) OVER (
            PARTITION BY stream_type, stream_id ORDER BY version
        ) AS prev_recorded_at,
        lag(version) OVER (
            PARTITION BY stream_type, stream_id ORDER BY version
        ) AS prev_version
    FROM events
)
SELECT stream_type, stream_id, prev_version AS v1, version AS v2
FROM ordered
WHERE prev_recorded_at IS NOT NULL AND recorded_at < prev_recorded_at
"""

_TIME_INVERSION_QUERY = """
SELECT event_id, occurred_at, recorded_at
FROM events
WHERE occurred_at > recorded_at + INTERVAL '5 seconds'
"""

_ORPHAN_CAUSATION_QUERY = """
SELECT a.event_id, a.causation_id
FROM events a
WHERE a.causation_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM events b WHERE b.event_id = a.causation_id)
"""
