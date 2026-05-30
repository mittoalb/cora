"""Application-handler tests for the `sign_seal_pointer` slice.

Covers the authz denial path (no event written), the FSM precondition
rejection on non-Live source-states (Republishing), not-found on an
unknown facility's Seal, head-hash validation propagation from the
decider, strict-not-idempotent posture on monotonic-sequence replay,
and the success path's event envelope shape (correlation_id,
causation_id, and the `signed_by_actor_id` denorm on payload).
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.federation.aggregates.seal import (
    SealCannotSignError,
    SealNotFoundError,
    SealSequenceNumberRegressionError,
)
from cora.federation.aggregates.seal._stream_id import seal_stream_id
from cora.federation.errors import UnauthorizedError
from cora.federation.features import sign_seal_pointer
from cora.federation.features.sign_seal_pointer import SignSealPointer
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.federation._helpers import seed_live_seal, seed_republishing_seal

_T0 = datetime(2026, 5, 30, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 5, 30, 11, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_FACILITY_ID = "aps-2bm"
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed101")
_START_REPUB_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed102")
_NEXT_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed103")
_FOLLOWUP_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed104")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_OTHER_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000088")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_NEW_HEAD_HASH = "b" * 64
_LATER_HEAD_HASH = "c" * 64


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
    ids: list[UUID] | None = None,
) -> Kernel:
    return _build_deps_shared(
        ids=ids if ids is not None else [_NEXT_EVENT_ID],
        now=_T2,
        event_store=event_store,
        deny=deny,
    )


def _command(
    *,
    new_head_hash: str = _NEW_HEAD_HASH,
    new_sequence_number: int = 1,
) -> SignSealPointer:
    return SignSealPointer(
        facility_id=_FACILITY_ID,
        new_head_hash=new_head_hash,
        new_sequence_number=new_sequence_number,
    )


@pytest.mark.unit
async def test_sign_seal_pointer_handler_appends_event_to_live_seal() -> None:
    store = InMemoryEventStore()
    await seed_live_seal(
        store,
        stream_id=seal_stream_id(_FACILITY_ID),
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store)
    handler = sign_seal_pointer.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Seal", seal_stream_id(_FACILITY_ID))
    assert version == 2
    stored = events[-1]
    assert stored.event_type == "SealPointerSigned"
    assert stored.payload["facility_id"] == _FACILITY_ID
    assert stored.payload["head_hash"] == _NEW_HEAD_HASH
    assert stored.payload["sequence_number"] == 1
    assert stored.payload["signed_by_actor_id"] == str(_PRINCIPAL_ID)
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None


@pytest.mark.unit
async def test_sign_seal_pointer_handler_propagates_causation_id() -> None:
    """Optional `causation_id` on the request envelope rides through to the event."""
    store = InMemoryEventStore()
    await seed_live_seal(
        store,
        stream_id=seal_stream_id(_FACILITY_ID),
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        facility_id=_FACILITY_ID,
    )
    causation = UUID("01900000-0000-7000-8000-0000000000cc")
    deps = _build_deps(event_store=store)
    handler = sign_seal_pointer.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )
    events, _ = await store.load("Seal", seal_stream_id(_FACILITY_ID))
    assert events[-1].causation_id == causation


@pytest.mark.unit
async def test_sign_seal_pointer_handler_raises_not_found_for_unknown_facility() -> None:
    deps = _build_deps()
    handler = sign_seal_pointer.bind(deps)
    with pytest.raises(SealNotFoundError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_sign_seal_pointer_handler_raises_cannot_sign_when_republishing() -> None:
    """A Republishing Seal cannot accept a signing event; handler raises."""
    store = InMemoryEventStore()
    await seed_republishing_seal(
        store,
        stream_id=seal_stream_id(_FACILITY_ID),
        genesis_event_id=_GENESIS_EVENT_ID,
        start_event_id=_START_REPUB_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        republishing_started_at=_T1,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store)
    handler = sign_seal_pointer.bind(deps)
    with pytest.raises(SealCannotSignError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_sign_seal_pointer_handler_raises_on_empty_new_head_hash() -> None:
    """Decider-layer head-hash validation surfaces through the handler."""
    store = InMemoryEventStore()
    await seed_live_seal(
        store,
        stream_id=seal_stream_id(_FACILITY_ID),
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store)
    handler = sign_seal_pointer.bind(deps)
    with pytest.raises(ValueError, match="new_head_hash"):
        await handler(
            _command(new_head_hash="   "),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_sign_seal_pointer_handler_raises_sequence_regression_on_lower_seq() -> None:
    """Supplying a sequence number that does not strictly exceed the prior rejects."""
    store = InMemoryEventStore()
    await seed_live_seal(
        store,
        stream_id=seal_stream_id(_FACILITY_ID),
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store, ids=[_NEXT_EVENT_ID, _FOLLOWUP_EVENT_ID])
    handler = sign_seal_pointer.bind(deps)
    await handler(
        _command(new_sequence_number=5),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(SealSequenceNumberRegressionError):
        await handler(
            _command(new_head_hash=_LATER_HEAD_HASH, new_sequence_number=5),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_sign_seal_pointer_handler_raises_cannot_sign_when_sequence_regresses() -> None:
    """A lower-than-prior sequence number also surfaces as regression."""
    store = InMemoryEventStore()
    await seed_live_seal(
        store,
        stream_id=seal_stream_id(_FACILITY_ID),
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store, ids=[_NEXT_EVENT_ID, _FOLLOWUP_EVENT_ID])
    handler = sign_seal_pointer.bind(deps)
    await handler(
        _command(new_sequence_number=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(SealSequenceNumberRegressionError):
        await handler(
            _command(new_head_hash=_LATER_HEAD_HASH, new_sequence_number=4),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_sign_seal_pointer_handler_denies_via_authorize_port() -> None:
    store = InMemoryEventStore()
    await seed_live_seal(
        store,
        stream_id=seal_stream_id(_FACILITY_ID),
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store, deny=True)
    handler = sign_seal_pointer.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_sign_seal_pointer_handler_denied_does_not_write_to_stream() -> None:
    """Authz-denial MUST NOT leave events on the stream."""
    store = InMemoryEventStore()
    await seed_live_seal(
        store,
        stream_id=seal_stream_id(_FACILITY_ID),
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store, deny=True)
    handler = sign_seal_pointer.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Seal", seal_stream_id(_FACILITY_ID))
    assert version == 1  # untouched after SealInitialized seed


@pytest.mark.unit
async def test_sign_seal_pointer_handler_records_signed_by_actor_id() -> None:
    """The handler injects the request envelope's `principal_id` as
    `signed_by_actor_id` on the emitted event, regardless of who
    initialised the Seal."""
    store = InMemoryEventStore()
    await seed_live_seal(
        store,
        stream_id=seal_stream_id(_FACILITY_ID),
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_OTHER_PRINCIPAL_ID,
        initialized_at=_T0,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store)
    handler = sign_seal_pointer.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Seal", seal_stream_id(_FACILITY_ID))
    assert events[-1].payload["signed_by_actor_id"] == str(_PRINCIPAL_ID)


@pytest.mark.unit
async def test_sign_seal_pointer_handler_captures_signed_at_from_clock() -> None:
    """`signed_at` payload field reuses the same wall-clock as the envelope's
    `occurred_at`, sourced from `deps.clock.now()` per capture-don't-recompute."""
    store = InMemoryEventStore()
    await seed_live_seal(
        store,
        stream_id=seal_stream_id(_FACILITY_ID),
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store)
    handler = sign_seal_pointer.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Seal", seal_stream_id(_FACILITY_ID))
    assert events[-1].payload["signed_at"] == _T2.isoformat()
    assert events[-1].occurred_at == _T2


@pytest.mark.unit
async def test_sign_seal_pointer_handler_accepts_monotonic_sequence_chain() -> None:
    """Two successful signings in sequence with strictly-increasing numbers."""
    store = InMemoryEventStore()
    await seed_live_seal(
        store,
        stream_id=seal_stream_id(_FACILITY_ID),
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store, ids=[_NEXT_EVENT_ID, _FOLLOWUP_EVENT_ID])
    handler = sign_seal_pointer.bind(deps)
    await handler(
        _command(new_sequence_number=1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await handler(
        _command(new_head_hash=_LATER_HEAD_HASH, new_sequence_number=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Seal", seal_stream_id(_FACILITY_ID))
    assert version == 3
    assert events[-2].payload["sequence_number"] == 1
    assert events[-1].payload["sequence_number"] == 2
    assert events[-1].payload["head_hash"] == _LATER_HEAD_HASH
