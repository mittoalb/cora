"""Unit tests for `InMemoryEventStore`. Mirrors the Postgres adapter's contract."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.ports.event_store import ConcurrencyError, NewEvent


def _event(payload: dict[str, object] | None = None) -> NewEvent:
    return NewEvent(
        event_type="Recorded",
        schema_version=1,
        payload=payload or {"k": "v"},
        occurred_at=datetime.now(tz=UTC),
        correlation_id=uuid4(),
        causation_id=None,
        metadata={},
    )


@pytest.mark.unit
async def test_load_returns_empty_for_unknown_stream() -> None:
    store = InMemoryEventStore()
    events, version = await store.load("Actor", uuid4())
    assert events == []
    assert version == 0


@pytest.mark.unit
async def test_append_then_load_round_trip() -> None:
    store = InMemoryEventStore()
    stream_id = uuid4()
    new_version = await store.append("Actor", stream_id, 0, [_event({"i": i}) for i in range(3)])
    assert new_version == 3

    loaded, version = await store.load("Actor", stream_id)
    assert version == 3
    assert [e.version for e in loaded] == [1, 2, 3]
    assert [e.payload["i"] for e in loaded] == [0, 1, 2]
    assert all(e.position > 0 for e in loaded)


@pytest.mark.unit
async def test_append_raises_concurrency_error_on_stale_expected_version() -> None:
    store = InMemoryEventStore()
    stream_id = uuid4()
    await store.append("Actor", stream_id, 0, [_event()])

    with pytest.raises(ConcurrencyError) as exc_info:
        await store.append("Actor", stream_id, 0, [_event()])

    assert exc_info.value.expected == 0
    assert exc_info.value.actual == 1


@pytest.mark.unit
async def test_payload_is_deep_copied_on_append() -> None:
    """Mutating the original payload after append must not affect stored event."""
    store = InMemoryEventStore()
    stream_id = uuid4()
    payload: dict[str, object] = {"items": [1, 2, 3]}
    await store.append("Actor", stream_id, 0, [_event(payload)])

    payload["items"] = [99]  # type: ignore[assignment]

    loaded, _ = await store.load("Actor", stream_id)
    assert loaded[0].payload == {"items": [1, 2, 3]}


@pytest.mark.unit
async def test_streams_are_isolated_by_type_and_id() -> None:
    store = InMemoryEventStore()
    actor_id = uuid4()
    await store.append("Actor", actor_id, 0, [_event()])
    await store.append("Equipment", actor_id, 0, [_event()])

    actor_events, actor_v = await store.load("Actor", actor_id)
    equip_events, equip_v = await store.load("Equipment", actor_id)
    assert actor_v == 1
    assert equip_v == 1
    assert actor_events[0].position != equip_events[0].position


@pytest.mark.unit
async def test_empty_event_list_is_a_noop() -> None:
    store = InMemoryEventStore()
    stream_id = uuid4()
    new_version = await store.append("Actor", stream_id, 0, [])
    assert new_version == 0
    events, version = await store.load("Actor", stream_id)
    assert events == []
    assert version == 0
