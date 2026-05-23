"""Round-trip integration tests for the `principal_id`
hook on the event envelope.

Pins three properties of the column-and-port-and-adapter chain
before any handler is wired:

  1. NULL principal_id round-trips (the historical / pre-hook
     case; field absent on append, NULL on load).
  2. Non-NULL principal_id round-trips through the asyncpg UUID
     codec on both write and read.
  3. Per-event distinct principal_id values are preserved
     individually within a single batch, not collapsed.

Sister test [test_event_store_principal_id_inmemory.py] pins the
same properties on the InMemory adapter so the two adapters agree
at the contract level.
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
    principal_id: UUID | None = None,
    payload: dict[str, object] | None = None,
) -> NewEvent:
    return NewEvent(
        event_id=uuid4(),
        event_type="Recorded",
        schema_version=1,
        payload=payload or {"k": "v"},
        occurred_at=datetime.now(tz=UTC),
        correlation_id=uuid4(),
        causation_id=None,
        metadata={},
        principal_id=principal_id,
    )


@pytest.mark.integration
async def test_null_principal_id_round_trips(db_pool: asyncpg.Pool) -> None:
    """The pre-hook historical case: append without
    setting principal_id, load back, see None on the StoredEvent."""
    store = PostgresEventStore(db_pool)
    stream_id = uuid4()
    await store.append("Actor", stream_id, 0, [_make_event(principal_id=None)])

    loaded, _ = await store.load("Actor", stream_id)
    assert len(loaded) == 1
    assert loaded[0].principal_id is None


@pytest.mark.integration
async def test_non_null_principal_id_round_trips(db_pool: asyncpg.Pool) -> None:
    """The post-hook case: append with a real UUID, get the same
    UUID back from load (proves asyncpg codec works in both
    directions for the new column)."""
    store = PostgresEventStore(db_pool)
    stream_id = uuid4()
    principal = UUID("01900000-0000-7000-8000-00000000aa11")
    await store.append("Actor", stream_id, 0, [_make_event(principal_id=principal)])

    loaded, _ = await store.load("Actor", stream_id)
    assert len(loaded) == 1
    assert loaded[0].principal_id == principal


@pytest.mark.integration
async def test_per_event_principal_ids_preserved_within_batch(
    db_pool: asyncpg.Pool,
) -> None:
    """A single append batch can carry events from different
    principals (in-bound saga / process-manager case where a
    chain crosses principal boundaries). Each event must keep
    its own principal_id, not all collapse to one."""
    store = PostgresEventStore(db_pool)
    stream_id = uuid4()
    p1 = UUID("01900000-0000-7000-8000-00000000aa01")
    p2 = UUID("01900000-0000-7000-8000-00000000aa02")
    await store.append(
        "Actor",
        stream_id,
        0,
        [
            _make_event(principal_id=p1, payload={"step": 0}),
            _make_event(principal_id=p2, payload={"step": 1}),
            _make_event(principal_id=None, payload={"step": 2}),
        ],
    )

    loaded, _ = await store.load("Actor", stream_id)
    assert [e.principal_id for e in loaded] == [p1, p2, None]


@pytest.mark.integration
async def test_principal_id_does_not_affect_existing_envelope_fields(
    db_pool: asyncpg.Pool,
) -> None:
    """Belt-and-suspenders regression check: the new column write
    didn't disturb the other envelope fields (correlation, causation,
    metadata, occurred_at, schema_version)."""
    store = PostgresEventStore(db_pool)
    stream_id = uuid4()
    principal = UUID("01900000-0000-7000-8000-00000000aa33")
    correlation = UUID("01900000-0000-7000-8000-00000000aa34")
    causation = UUID("01900000-0000-7000-8000-00000000aa35")

    event = NewEvent(
        event_id=uuid4(),
        event_type="Recorded",
        schema_version=7,
        payload={"k": "v"},
        occurred_at=datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC),
        correlation_id=correlation,
        causation_id=causation,
        metadata={"command": "TestCommand"},
        principal_id=principal,
    )
    await store.append("Actor", stream_id, 0, [event])

    loaded, _ = await store.load("Actor", stream_id)
    assert len(loaded) == 1
    stored = loaded[0]
    assert stored.principal_id == principal
    assert stored.correlation_id == correlation
    assert stored.causation_id == causation
    assert stored.schema_version == 7
    assert stored.metadata == {"command": "TestCommand"}
    assert stored.occurred_at == datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)
