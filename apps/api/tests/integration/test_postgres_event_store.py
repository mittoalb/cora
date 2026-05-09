"""Integration tests for `PostgresEventStore` against a real Postgres."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import asyncpg
import pytest

from cora.infrastructure.ports.event_store import (
    ConcurrencyError,
    NewEvent,
)
from cora.infrastructure.postgres.event_store import PostgresEventStore


def _make_event(
    *,
    event_type: str = "Recorded",
    payload: dict[str, object] | None = None,
) -> NewEvent:
    return NewEvent(
        event_type=event_type,
        schema_version=1,
        payload=payload or {"k": "v"},
        occurred_at=datetime.now(tz=UTC),
        correlation_id=uuid4(),
        causation_id=None,
        metadata={"actor": "test"},
    )


@pytest.mark.integration
async def test_load_returns_empty_for_unknown_stream(
    db_pool: asyncpg.Pool,
) -> None:
    store = PostgresEventStore(db_pool)
    events, version = await store.load("Actor", uuid4())
    assert events == []
    assert version == 0


@pytest.mark.integration
async def test_append_then_load_round_trip(db_pool: asyncpg.Pool) -> None:
    store = PostgresEventStore(db_pool)
    stream_id = uuid4()
    new_events = [_make_event(payload={"step": i}) for i in range(3)]

    new_version = await store.append("Actor", stream_id, 0, new_events)
    assert new_version == 3

    loaded, version = await store.load("Actor", stream_id)
    assert version == 3
    assert [e.version for e in loaded] == [1, 2, 3]
    assert [e.payload["step"] for e in loaded] == [0, 1, 2]
    assert all(e.position > 0 for e in loaded)
    assert all(e.metadata == {"actor": "test"} for e in loaded)


@pytest.mark.integration
async def test_append_raises_concurrency_error_on_stale_expected_version(
    db_pool: asyncpg.Pool,
) -> None:
    store = PostgresEventStore(db_pool)
    stream_id = uuid4()
    await store.append("Actor", stream_id, 0, [_make_event()])

    with pytest.raises(ConcurrencyError) as exc_info:
        await store.append("Actor", stream_id, 0, [_make_event()])

    assert exc_info.value.expected == 0
    assert exc_info.value.actual == 1
    assert exc_info.value.stream_type == "Actor"
    assert exc_info.value.stream_id == stream_id


@pytest.mark.integration
async def test_append_is_atomic_on_partial_conflict(
    db_pool: asyncpg.Pool,
) -> None:
    """If any event in a batch conflicts, none should be persisted."""
    store = PostgresEventStore(db_pool)
    stream_id = uuid4()
    await store.append("Actor", stream_id, 0, [_make_event()])

    with pytest.raises(ConcurrencyError):
        await store.append(
            "Actor",
            stream_id,
            0,
            [_make_event(), _make_event(), _make_event()],
        )

    loaded, version = await store.load("Actor", stream_id)
    assert version == 1
    assert len(loaded) == 1


@pytest.mark.integration
async def test_streams_are_isolated_by_type_and_id(
    db_pool: asyncpg.Pool,
) -> None:
    store = PostgresEventStore(db_pool)
    actor_id = uuid4()
    other_id = uuid4()

    await store.append("Actor", actor_id, 0, [_make_event()])
    await store.append("Equipment", actor_id, 0, [_make_event()])
    await store.append("Actor", other_id, 0, [_make_event()])

    actor_events, actor_v = await store.load("Actor", actor_id)
    equip_events, equip_v = await store.load("Equipment", actor_id)
    other_events, other_v = await store.load("Actor", other_id)

    assert actor_v == equip_v == other_v == 1
    positions = {e.position for e in actor_events + equip_events + other_events}
    assert len(positions) == 3


@pytest.mark.integration
async def test_append_emits_pg_notify(db_pool: asyncpg.Pool) -> None:
    """The AFTER INSERT trigger should fire pg_notify on each event."""
    received: list[tuple[str, str]] = []

    listener = await db_pool.acquire()
    try:

        def _on_notify(
            _conn: object,
            _pid: int,
            channel: str,
            payload: str,
        ) -> None:
            received.append((channel, payload))

        await listener.add_listener("events", _on_notify)
        store = PostgresEventStore(db_pool)
        stream_id = uuid4()
        await store.append("Actor", stream_id, 0, [_make_event(), _make_event()])

        for _ in range(20):
            if len(received) >= 2:
                break
            await asyncio.sleep(0.05)

        await listener.remove_listener("events", _on_notify)
    finally:
        await db_pool.release(listener)

    assert len(received) == 2
    assert all(channel == "events" for channel, _ in received)
