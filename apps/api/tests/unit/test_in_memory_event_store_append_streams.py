"""Unit tests for `InMemoryEventStore.append_streams`.

Pins the multi-stream atomic-write contract: all-or-nothing across
streams, per-stream version checks, shared transaction_id, event_id
uniqueness across the entire batch.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.ports.event_store import ConcurrencyError, NewEvent, StreamAppend


def _event(payload: dict[str, object] | None = None) -> NewEvent:
    return NewEvent(
        event_id=uuid4(),
        event_type="Recorded",
        schema_version=1,
        payload=payload or {"k": "v"},
        occurred_at=datetime.now(tz=UTC),
        correlation_id=uuid4(),
        causation_id=None,
        metadata={},
        principal_id=uuid4(),
    )


@pytest.mark.unit
async def test_append_streams_writes_to_two_streams_atomically() -> None:
    store = InMemoryEventStore()
    parent_id, child_id = uuid4(), uuid4()

    versions = await store.append_streams(
        [
            StreamAppend("Clearance", parent_id, expected_version=0, events=[_event()]),
            StreamAppend("Clearance", child_id, expected_version=0, events=[_event(), _event()]),
        ]
    )
    assert versions == {parent_id: 1, child_id: 2}

    parent_events, _ = await store.load("Clearance", parent_id)
    child_events, _ = await store.load("Clearance", child_id)
    assert len(parent_events) == 1
    assert len(child_events) == 2


@pytest.mark.unit
async def test_append_streams_assigns_shared_transaction_id_across_streams() -> None:
    """All events in one append_streams call share the same fake xid8.
    Mirrors Postgres's "one transaction = one xid8" semantic so the
    projection cursor sees the multi-stream batch as one atomic step."""
    store = InMemoryEventStore()
    parent_id, child_id = uuid4(), uuid4()

    await store.append_streams(
        [
            StreamAppend("Clearance", parent_id, expected_version=0, events=[_event()]),
            StreamAppend("Clearance", child_id, expected_version=0, events=[_event()]),
        ]
    )
    parent_events, _ = await store.load("Clearance", parent_id)
    child_events, _ = await store.load("Clearance", child_id)
    assert parent_events[0].transaction_id == child_events[0].transaction_id


@pytest.mark.unit
async def test_append_streams_rolls_back_when_one_stream_has_wrong_expected_version() -> None:
    """All-or-nothing: the second stream's expected_version mismatch
    aborts the whole batch; the first stream stays untouched."""
    store = InMemoryEventStore()
    parent_id, child_id = uuid4(), uuid4()
    # Seed parent so its current version is 1
    await store.append("Clearance", parent_id, expected_version=0, events=[_event()])

    with pytest.raises(ConcurrencyError) as exc_info:
        await store.append_streams(
            [
                # Parent expects version 1 (matches reality)
                StreamAppend("Clearance", parent_id, expected_version=1, events=[_event()]),
                # Child expects version 5 (mismatch: actual is 0)
                StreamAppend("Clearance", child_id, expected_version=5, events=[_event()]),
            ]
        )
    assert exc_info.value.stream_id == child_id
    assert exc_info.value.expected == 5
    assert exc_info.value.actual == 0

    # Parent unchanged (still at version 1 from the seed)
    parent_events, parent_v = await store.load("Clearance", parent_id)
    assert parent_v == 1
    assert len(parent_events) == 1
    # Child stays empty (the batch never committed)
    child_events, child_v = await store.load("Clearance", child_id)
    assert child_v == 0
    assert child_events == []


@pytest.mark.unit
async def test_append_streams_rejects_duplicate_event_id_across_streams() -> None:
    """event_id UNIQUE constraint spans the entire multi-stream batch."""
    store = InMemoryEventStore()
    shared_id = uuid4()
    e1 = _event()
    e2 = NewEvent(
        event_id=shared_id,  # collide with e1's id
        event_type="Recorded",
        schema_version=1,
        payload={},
        occurred_at=datetime.now(tz=UTC),
        correlation_id=uuid4(),
        causation_id=None,
        metadata={},
        principal_id=uuid4(),
    )
    e3 = NewEvent(
        event_id=shared_id,
        event_type="Recorded",
        schema_version=1,
        payload={},
        occurred_at=datetime.now(tz=UTC),
        correlation_id=uuid4(),
        causation_id=None,
        metadata={},
        principal_id=uuid4(),
    )
    _ = e1

    parent_id, child_id = uuid4(), uuid4()
    with pytest.raises(ValueError, match="Duplicate event_id"):
        await store.append_streams(
            [
                StreamAppend("Clearance", parent_id, expected_version=0, events=[e2]),
                StreamAppend("Clearance", child_id, expected_version=0, events=[e3]),
            ]
        )
    # Neither stream was mutated
    parent_events, _ = await store.load("Clearance", parent_id)
    child_events, _ = await store.load("Clearance", child_id)
    assert parent_events == []
    assert child_events == []


@pytest.mark.unit
async def test_append_streams_with_empty_events_is_noop_per_stream() -> None:
    """A StreamAppend with empty events list is a no-op (reports the
    expected_version unchanged); a fully-empty batch is a no-op overall."""
    store = InMemoryEventStore()
    s1, s2 = uuid4(), uuid4()
    versions = await store.append_streams(
        [
            StreamAppend("Clearance", s1, expected_version=0, events=[]),
            StreamAppend("Clearance", s2, expected_version=3, events=[]),
        ]
    )
    assert versions == {s1: 0, s2: 3}


@pytest.mark.unit
async def test_append_streams_mixes_empty_and_non_empty_stream_appends() -> None:
    """A no-op stream alongside a real append still gets its
    expected_version reported back."""
    store = InMemoryEventStore()
    written_id = uuid4()
    noop_id = uuid4()
    versions = await store.append_streams(
        [
            StreamAppend("Clearance", written_id, expected_version=0, events=[_event()]),
            StreamAppend("Clearance", noop_id, expected_version=0, events=[]),
        ]
    )
    assert versions == {written_id: 1, noop_id: 0}


@pytest.mark.unit
async def test_append_single_stream_delegates_through_append_streams() -> None:
    """`append` is now a wrapper around `append_streams`. Round-trip
    behavior should be byte-identical to the multi-stream path."""
    store = InMemoryEventStore()
    stream_id = uuid4()
    new_version = await store.append(
        "Clearance", stream_id, expected_version=0, events=[_event(), _event()]
    )
    assert new_version == 2
    events, version = await store.load("Clearance", stream_id)
    assert version == 2
    assert len(events) == 2


# ---------- Per-event signature plumbing ----------


def _signed_event(
    payload: dict[str, object] | None = None,
    *,
    signature: bytes | None = None,
    signature_kid: str | None = None,
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
        principal_id=uuid4(),
        signature=signature,
        signature_kid=signature_kid,
    )


@pytest.mark.unit
async def test_append_without_signature_loads_back_as_none() -> None:
    store = InMemoryEventStore()
    stream_id = uuid4()
    await store.append("Clearance", stream_id, expected_version=0, events=[_event()])
    events, _ = await store.load("Clearance", stream_id)
    assert events[0].signature is None
    assert events[0].signature_kid is None


@pytest.mark.unit
async def test_append_with_signature_round_trips() -> None:
    store = InMemoryEventStore()
    stream_id = uuid4()
    signature = b"\x42" * 64
    kid = "kid-test-12345"
    await store.append(
        "Clearance",
        stream_id,
        expected_version=0,
        events=[_signed_event(signature=signature, signature_kid=kid)],
    )
    events, _ = await store.load("Clearance", stream_id)
    assert events[0].signature == signature
    assert events[0].signature_kid == kid


@pytest.mark.unit
async def test_append_mixed_batch_preserves_per_event_signature_state() -> None:
    """Per-event signature state must stay distinct across a batch.
    A regression that hoisted signature to batch-level would silently
    corrupt every mixed batch."""
    store = InMemoryEventStore()
    stream_id = uuid4()
    await store.append(
        "Clearance",
        stream_id,
        expected_version=0,
        events=[
            _signed_event(
                payload={"k": "signed"},
                signature=b"\x01" * 64,
                signature_kid="kid-A",
            ),
            _signed_event(payload={"k": "unsigned"}),
        ],
    )
    events, _ = await store.load("Clearance", stream_id)
    assert events[0].signature_kid == "kid-A"
    assert events[1].signature is None
    assert events[1].signature_kid is None
