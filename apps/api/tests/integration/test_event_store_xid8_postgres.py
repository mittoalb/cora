"""Phase-8e prep: pin `events.transaction_id` semantics under real Postgres.

The xid8 column added in migration `20260512240000_add_transaction_id`
is the foundation of the projection-worker advance cursor. This test
guards three properties projections will rely on:

  1. INSERTs auto-populate transaction_id with `pg_current_xact_id()`
     (the application never writes the column).
  2. All events in the SAME `append()` call share the SAME
     transaction_id (one transaction per batch).
  3. Events in different `append()` calls get strictly-increasing
     transaction_ids (xid8 is monotonic).

Also pins that asyncpg's `transaction_id::text` cast round-trips
cleanly to a Python `int` via `_row_to_event` (the Khyst pattern,
since asyncpg has no built-in xid8 codec as of 0.31).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import uuid4

import asyncpg
import pytest

from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.event_envelope import to_new_event


def _new(*, occurred_at: datetime) -> object:
    """Build a NewEvent with minimal payload."""
    return to_new_event(
        event_type="SmokeTested",
        payload={"hello": "world"},
        occurred_at=occurred_at,
        event_id=uuid4(),
        command_name="SmokeTest",
        correlation_id=uuid4(),
        principal_id=uuid4(),
    )


@pytest.mark.integration
async def test_transaction_id_auto_populates_on_insert(
    db_pool: asyncpg.Pool,
) -> None:
    """Single event append: column populates with a non-zero xid8 value."""
    store = PostgresEventStore(db_pool)
    stream_id = uuid4()
    now = datetime.now(tz=UTC)

    await store.append("SmokeStream", stream_id, 0, [_new(occurred_at=now)])  # type: ignore[arg-type]
    events, _ = await store.load("SmokeStream", stream_id)

    assert len(events) == 1
    assert events[0].transaction_id > 0


@pytest.mark.integration
async def test_events_in_same_append_share_transaction_id(
    db_pool: asyncpg.Pool,
) -> None:
    """N events in one batch -> one transaction -> one xid8."""
    store = PostgresEventStore(db_pool)
    stream_id = uuid4()
    now = datetime.now(tz=UTC)

    await store.append(
        "SmokeStream",
        stream_id,
        0,
        [_new(occurred_at=now), _new(occurred_at=now), _new(occurred_at=now)],  # type: ignore[arg-type]
    )
    events, _ = await store.load("SmokeStream", stream_id)

    tx_ids = {e.transaction_id for e in events}
    assert len(events) == 3
    assert len(tx_ids) == 1, (
        f"Events appended in one batch should share transaction_id; got {sorted(tx_ids)}"
    )


@pytest.mark.integration
async def test_separate_appends_get_strictly_increasing_transaction_ids(
    db_pool: asyncpg.Pool,
) -> None:
    """Distinct append() calls -> distinct transactions -> monotonic xid8."""
    store = PostgresEventStore(db_pool)
    stream_a = uuid4()
    stream_b = uuid4()
    now = datetime.now(tz=UTC)

    await store.append("SmokeStream", stream_a, 0, [_new(occurred_at=now)])  # type: ignore[arg-type]
    await store.append("SmokeStream", stream_b, 0, [_new(occurred_at=now)])  # type: ignore[arg-type]

    events_a, _ = await store.load("SmokeStream", stream_a)
    events_b, _ = await store.load("SmokeStream", stream_b)
    assert events_b[0].transaction_id > events_a[0].transaction_id


@pytest.mark.integration
async def test_advance_index_exists_on_transaction_id_position(
    db_pool: asyncpg.Pool,
) -> None:
    """Pin: the projection-advance index actually landed in the per-test
    template DB. Without it, projection-advance queries fall back to a
    sort that scales with table size."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'events' AND indexname = 'events_advance_idx'
            """
        )
    assert row is not None, "events_advance_idx missing; migration didn't apply"


@pytest.mark.integration
async def test_transaction_id_uses_xid8_type(
    db_pool: asyncpg.Pool,
) -> None:
    """Pin: column type is xid8 (not bigint or text). Catches a future
    migration that accidentally changes the column type."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT data_type FROM information_schema.columns
            WHERE table_name = 'events' AND column_name = 'transaction_id'
            """
        )
    assert row is not None
    assert str(row["data_type"]) == "xid8", f"Expected xid8, got {row['data_type']}"


@pytest.mark.integration
async def test_events_table_xid8_compares_with_pg_snapshot_xmin(
    db_pool: asyncpg.Pool,
) -> None:
    """Pin: the canonical advance-query exclusion shape works syntactically.
    Inserts an event, then runs the projection-shaped query that uses
    `transaction_id < pg_snapshot_xmin(pg_current_snapshot())` to confirm
    the SQL parses + executes (catches typos in the locked-in pattern)."""
    store = PostgresEventStore(db_pool)
    stream_id = uuid4()
    await store.append(
        "SmokeStream",
        stream_id,
        0,
        [_new(occurred_at=datetime.now(tz=UTC))],  # type: ignore[arg-type]
    )

    async with db_pool.acquire() as conn:
        # Use a fresh snapshot in a separate session so the just-inserted
        # event's transaction is no longer in-flight.
        rows = await conn.fetch(
            """
            SELECT position, transaction_id::text AS tx
            FROM events
            WHERE (transaction_id, position) > ('0'::xid8, 0)
              AND transaction_id < pg_snapshot_xmin(pg_current_snapshot())
            ORDER BY transaction_id, position
            LIMIT 10
            """
        )
    assert len(rows) >= 1, (
        "Advance query returned zero rows; the event should have been "
        "visible after its transaction committed."
    )


@pytest.mark.integration
async def test_xid8_sentinel_zero_compares_less_than_real_values(
    db_pool: asyncpg.Pool,
) -> None:
    """Pin: `'0'::xid8` (the projection bookmark sentinel for first-run
    registration) compares strictly less than every real xid8 we'd see.
    Phase-8e bookmark schema uses `last_transaction_id xid8 DEFAULT '0'::xid8`
    so first-run subscriptions replay from the start."""
    store = PostgresEventStore(db_pool)
    stream_id = uuid4()
    await store.append(
        "SmokeStream",
        stream_id,
        0,
        [_new(occurred_at=datetime.now(tz=UTC))],  # type: ignore[arg-type]
    )
    events, _ = await store.load("SmokeStream", stream_id)

    async with db_pool.acquire() as conn:
        # asyncpg's parameter binding accepts a Python int and the
        # `$1::xid8` cast converts on the server side. Empirically
        # confirmed under PG18 + asyncpg 0.31; if asyncpg ever ships
        # a native xid8 codec, this test stays correct.
        is_less = await conn.fetchval(
            "SELECT '0'::xid8 < $1::xid8",
            events[0].transaction_id,
        )
    assert bool(is_less), (
        f"Sentinel '0'::xid8 should compare less than real xid8 "
        f"{events[0].transaction_id}; got False"
    )
