"""Round-trip unit tests for the Phase 9b-a `principal_id` hook on
the InMemoryEventStore adapter.

Mirrors the PG adapter's contract test
[test_event_store_principal_id_postgres.py] so the two adapters
agree at the contract level. If they ever diverge, the higher-up
handler tests fail uniformly across both fixtures rather than
silently in only one path.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.ports.event_store import NewEvent


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


@pytest.mark.unit
async def test_null_principal_id_round_trips() -> None:
    store = InMemoryEventStore()
    stream_id = uuid4()
    await store.append("Actor", stream_id, 0, [_make_event(principal_id=None)])

    loaded, _ = await store.load("Actor", stream_id)
    assert len(loaded) == 1
    assert loaded[0].principal_id is None


@pytest.mark.unit
async def test_non_null_principal_id_round_trips() -> None:
    store = InMemoryEventStore()
    stream_id = uuid4()
    principal = UUID("01900000-0000-7000-8000-00000000aa11")
    await store.append("Actor", stream_id, 0, [_make_event(principal_id=principal)])

    loaded, _ = await store.load("Actor", stream_id)
    assert len(loaded) == 1
    assert loaded[0].principal_id == principal


@pytest.mark.unit
async def test_per_event_principal_ids_preserved_within_batch() -> None:
    store = InMemoryEventStore()
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


@pytest.mark.unit
async def test_default_principal_id_is_none_when_kwarg_omitted() -> None:
    """Sanity: the dataclass default is None so existing call sites
    that don't yet pass the kwarg behave correctly during the Phase
    9b-a -> 9b-b transition window. (Helper-side default + pass-
    through tests live in `test_event_envelope.py` per its module
    docstring as the canonical home for the envelope helper.)"""
    event = NewEvent(
        event_id=uuid4(),
        event_type="Recorded",
        schema_version=1,
        payload={},
        occurred_at=datetime.now(tz=UTC),
        correlation_id=uuid4(),
    )
    assert event.principal_id is None
