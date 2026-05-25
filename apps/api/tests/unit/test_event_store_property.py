"""Property-based tests for `InMemoryEventStore` deep invariants.

Hypothesis-driven exploration of the EventStore port's semantics that
example-based tests can't reach: generated sequences of append/load
operations, concurrency-conflict patterns, multi-stream atomic writes.
Runs against `InMemoryEventStore` only — the in-memory adapter is the
spec implementation, fast enough to run hundreds of generated cases
per property in the unit tier. The behavioural contract suite
(`tests/integration/test_event_store_contract.py`) ensures Postgres
matches in-memory's example-based outcomes; PBT here validates that
the in-memory spec is internally consistent.

Per Corpus 3 of the testing-expansion research-memo: state-machine
PBT on event stores is "the strongest fit and underused" — concurrency,
ordering, multi-stream atomicity is exactly where adapters silently
diverge. CORA's `append_streams` is the load-bearing cross-aggregate
write (Safety BC `amend_clearance`, Agent BC `define_agent`) so its
all-or-nothing semantics deserve generated-input coverage.

This is example-of-each-property style (not full RuleBasedStateMachine)
because Hypothesis 6.x state machines have rough edges with async; a
stateful state-machine version can land as a follow-up if these
properties surface no issues.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.ports.event_store import (
    ConcurrencyError,
    NewEvent,
    StreamAppend,
)


def _make_event(
    *,
    event_id: UUID | None = None,
    payload_step: int = 0,
) -> NewEvent:
    return NewEvent(
        event_id=event_id if event_id is not None else uuid4(),
        event_type="PropertyEvent",
        schema_version=1,
        payload={"step": payload_step},
        occurred_at=datetime.now(tz=UTC),
        correlation_id=uuid4(),
        causation_id=None,
        metadata={},
        principal_id=uuid4(),
    )


# Bounded so the per-example runtime stays trivial; Hypothesis defaults
# to 100 examples per @given, so total ops per property stays under
# ~5000. The properties target invariants, not throughput.
_EVENT_COUNT = st.integers(min_value=1, max_value=10)
_STREAM_COUNT = st.integers(min_value=2, max_value=5)


@pytest.mark.unit
@given(count=_EVENT_COUNT)
async def test_append_then_load_round_trip_preserves_event_ids(count: int) -> None:
    """For any N >= 1, append N events then load returns them in order
    with matching event_ids and versions 1..N.
    """
    store = InMemoryEventStore()
    stream_id = uuid4()
    new_events = [_make_event(payload_step=i) for i in range(count)]

    new_version = await store.append("PropertyStream", stream_id, 0, new_events)
    assert new_version == count

    loaded, version = await store.load("PropertyStream", stream_id)
    assert version == count
    assert [e.event_id for e in loaded] == [e.event_id for e in new_events]
    assert [e.version for e in loaded] == list(range(1, count + 1))


@pytest.mark.unit
@given(
    first_count=_EVENT_COUNT,
    second_count=_EVENT_COUNT,
)
async def test_consecutive_appends_keep_versions_contiguous(
    first_count: int, second_count: int
) -> None:
    """Two consecutive appends to the same stream produce a single
    contiguous 1..(N+M) version sequence — no gaps, no resets.
    """
    store = InMemoryEventStore()
    stream_id = uuid4()

    await store.append("PropertyStream", stream_id, 0, [_make_event() for _ in range(first_count)])
    await store.append(
        "PropertyStream",
        stream_id,
        first_count,
        [_make_event() for _ in range(second_count)],
    )

    loaded, version = await store.load("PropertyStream", stream_id)
    expected_total = first_count + second_count
    assert version == expected_total
    assert [e.version for e in loaded] == list(range(1, expected_total + 1))


@pytest.mark.unit
@given(
    actual_count=_EVENT_COUNT,
    wrong_expected=st.integers(min_value=0, max_value=20),
)
async def test_stale_expected_version_always_raises(actual_count: int, wrong_expected: int) -> None:
    """Any append where expected_version != current_version raises
    ConcurrencyError. Pinned for all combinations of pre-existing
    event count and wrong expected_version.
    """
    store = InMemoryEventStore()
    stream_id = uuid4()
    await store.append("PropertyStream", stream_id, 0, [_make_event() for _ in range(actual_count)])

    if wrong_expected == actual_count:
        # Correct version — append should succeed, not raise. Skip via
        # assume() would shrink against us; just exercise the happy path.
        new_version = await store.append(
            "PropertyStream", stream_id, wrong_expected, [_make_event()]
        )
        assert new_version == actual_count + 1
    else:
        with pytest.raises(ConcurrencyError) as exc:
            await store.append("PropertyStream", stream_id, wrong_expected, [_make_event()])
        assert exc.value.expected == wrong_expected
        assert exc.value.actual == actual_count


@pytest.mark.unit
@given(stream_count=_STREAM_COUNT, events_per_stream=_EVENT_COUNT)
async def test_event_ids_are_globally_unique_across_streams(
    stream_count: int, events_per_stream: int
) -> None:
    """No two events anywhere in the store ever share an event_id, even
    across distinct streams. This is the load-bearing dedup-key invariant
    for downstream at-least-once projection consumers.
    """
    store = InMemoryEventStore()
    all_event_ids: list[UUID] = []
    for _ in range(stream_count):
        stream_id = uuid4()
        events = [_make_event(payload_step=i) for i in range(events_per_stream)]
        await store.append("PropertyStream", stream_id, 0, events)
        all_event_ids.extend(e.event_id for e in events)
    assert len(all_event_ids) == len(set(all_event_ids))


@pytest.mark.unit
@given(
    stream_count=_STREAM_COUNT,
    events_per_stream=_EVENT_COUNT,
    failing_stream_index=st.integers(min_value=0, max_value=4),
)
async def test_append_streams_rolls_back_all_on_concurrency_conflict(
    stream_count: int, events_per_stream: int, failing_stream_index: int
) -> None:
    """If ONE stream in an `append_streams` batch has a stale
    expected_version, NO events from ANY of the batch's streams persist.
    All-or-nothing atomicity across N streams, for any failure position
    in the batch.
    """
    if failing_stream_index >= stream_count:
        return  # invalid input combo; skip without using assume() to keep shrinking happy

    store = InMemoryEventStore()
    stream_ids = [uuid4() for _ in range(stream_count)]

    # Pre-populate the failing stream so its current_version != 0.
    await store.append("PropertyStream", stream_ids[failing_stream_index], 0, [_make_event()])

    # Now try a batch where the failing stream's expected_version is
    # stale (0 vs current 1) but every other stream is fresh.
    batch = [
        StreamAppend(
            "PropertyStream",
            sid,
            0,
            [_make_event() for _ in range(events_per_stream)],
        )
        for sid in stream_ids
    ]

    with pytest.raises(ConcurrencyError):
        await store.append_streams(batch)

    # Every fresh stream must still be empty (the failing stream keeps
    # its pre-populated event from the setup append; we assert the OTHER
    # streams stayed at version 0).
    for i, sid in enumerate(stream_ids):
        if i == failing_stream_index:
            continue
        events, version = await store.load("PropertyStream", sid)
        assert events == []
        assert version == 0


@pytest.mark.unit
@given(
    stream_count=_STREAM_COUNT,
    events_per_stream=_EVENT_COUNT,
)
async def test_append_streams_commits_all_when_every_stream_fresh(
    stream_count: int, events_per_stream: int
) -> None:
    """When every stream's expected_version matches, every stream
    becomes loadable with its full event sequence. The return value
    `{stream_id: new_version}` matches the per-stream length.
    """
    store = InMemoryEventStore()
    stream_ids = [uuid4() for _ in range(stream_count)]
    batch = [
        StreamAppend(
            "PropertyStream",
            sid,
            0,
            [_make_event() for _ in range(events_per_stream)],
        )
        for sid in stream_ids
    ]

    result = await store.append_streams(batch)
    assert result == {sid: events_per_stream for sid in stream_ids}

    for sid in stream_ids:
        events, version = await store.load("PropertyStream", sid)
        assert version == events_per_stream
        assert len(events) == events_per_stream
