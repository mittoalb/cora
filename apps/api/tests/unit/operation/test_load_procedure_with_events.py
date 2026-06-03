"""Unit tests for `load_procedure_with_events`.

Per [[project-run-procedure-replay-design]] §Operation BC seam
additions. The helper returns both the folded Procedure state AND
the raw StoredEvent list from a single `event_store.load` call;
`load_procedure` becomes a thin wrapper that discards the events.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports.event_store import StoredEvent
from cora.operation.aggregates.procedure import (
    ProcedureRegistered,
    event_type_name,
    load_procedure,
    load_procedure_with_events,
    to_payload,
)

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_registered(
    store: InMemoryEventStore,
    procedure_id: UUID,
) -> None:
    event = ProcedureRegistered(
        procedure_id=procedure_id,
        name="P",
        kind="bakeout",
        target_asset_ids=(),
        parent_run_id=None,
        capability_id=None,
        recipe_id=None,
        occurred_at=_NOW,
    )
    await store.append(
        stream_type="Procedure",
        stream_id=procedure_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="seed",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            ),
        ],
    )


@pytest.mark.unit
async def test_load_procedure_with_events_returns_folded_state_and_raw_event_list() -> None:
    store = InMemoryEventStore()
    procedure_id = uuid4()
    await _seed_registered(store, procedure_id)

    state, events = await load_procedure_with_events(store, procedure_id)

    assert state is not None
    assert state.id == procedure_id
    assert isinstance(events, list)
    assert len(events) == 1
    assert isinstance(events[0], StoredEvent)
    assert events[0].event_type == "ProcedureRegistered"


@pytest.mark.unit
async def test_load_procedure_with_events_with_empty_stream_returns_none_and_empty_list() -> None:
    store = InMemoryEventStore()

    state, events = await load_procedure_with_events(store, uuid4())

    assert state is None
    assert events == []


@pytest.mark.unit
async def test_load_procedure_returns_same_state_as_load_procedure_with_events_tuple_first() -> (
    None
):
    """Wrapper-parity: legacy `load_procedure` returns the same state
    as the first element of `load_procedure_with_events`'s tuple."""
    store = InMemoryEventStore()
    procedure_id = uuid4()
    await _seed_registered(store, procedure_id)

    state_a = await load_procedure(store, procedure_id)
    state_b, _events = await load_procedure_with_events(store, procedure_id)

    assert state_a == state_b


@pytest.mark.unit
async def test_load_procedure_with_events_uses_single_event_store_load_call() -> None:
    """Single underlying `event_store.load` call: a counter-spy
    asserts the helper does not double-IO."""

    class _CountingStore:
        def __init__(self, inner: InMemoryEventStore) -> None:
            self._inner = inner
            self.load_calls = 0

        async def load(self, stream_type: str, stream_id: UUID) -> tuple[list[StoredEvent], int]:
            self.load_calls += 1
            return await self._inner.load(stream_type, stream_id)

        async def append(self, **kwargs: object) -> None:  # type: ignore[override]
            await self._inner.append(**kwargs)  # type: ignore[arg-type]

    inner = InMemoryEventStore()
    procedure_id = uuid4()
    await _seed_registered(inner, procedure_id)
    counting = _CountingStore(inner)

    await load_procedure_with_events(counting, procedure_id)  # type: ignore[arg-type]

    assert counting.load_calls == 1
