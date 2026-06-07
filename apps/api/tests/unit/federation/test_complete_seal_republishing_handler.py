"""Application-handler tests for the `complete_seal_republishing` slice.

Covers the authz denial path (no event written), the FSM precondition
rejection on Live source-state, not-found on an unknown Seal,
strict-not-idempotent posture on replay against a now-Live Seal, the
pairing-invariant and sequence-regression decider rejections
propagated through the handler, and the success path's event envelope
shape (correlation_id, causation_id, and the `completed_by`
denorm on payload). The Seal is a per-facility singleton; the handler
derives the stream UUID deterministically via the canonical
`seal_stream_id` helper, so handler tests load the stream via the same
helper.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.federation.aggregates.seal import (
    SealCannotCompleteRepublishingError,
    SealNotFoundError,
    SealSequenceNumberRegressionError,
)
from cora.federation.aggregates.seal._stream_id import seal_stream_id
from cora.federation.errors import UnauthorizedError
from cora.federation.features import complete_seal_republishing
from cora.federation.features.complete_seal_republishing import (
    CompleteSealRepublishing,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.federation._helpers import (
    seed_live_seal,
    seed_republishing_seal,
)

_T0 = datetime(2026, 5, 30, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 5, 30, 11, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed101")
_START_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed102")
_NEXT_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed103")
_FOLLOWUP_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed104")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_OTHER_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000088")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_FACILITY_ID = "aps-2bm"
_NEW_HEAD_HASH = "b" * 64


def _seal_stream_id(facility_id: str = _FACILITY_ID) -> UUID:
    return seal_stream_id(facility_id)


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
    new_head_hash: str | None = _NEW_HEAD_HASH,
    new_sequence_number: int | None = 1,
) -> CompleteSealRepublishing:
    return CompleteSealRepublishing(
        facility_id=_FACILITY_ID,
        new_head_hash=new_head_hash,
        new_sequence_number=new_sequence_number,
    )


@pytest.mark.unit
async def test_complete_seal_republishing_handler_appends_event_to_republishing_seal() -> None:
    store = InMemoryEventStore()
    stream_id = _seal_stream_id()
    await seed_republishing_seal(
        store,
        stream_id=stream_id,
        genesis_event_id=_GENESIS_EVENT_ID,
        start_event_id=_START_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        republishing_started_at=_T1,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store)
    handler = complete_seal_republishing.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Seal", stream_id)
    assert version == 3
    stored = events[-1]
    assert stored.event_type == "SealRepublishingCompleted"
    assert stored.payload["facility_id"] == _FACILITY_ID
    assert stored.payload["new_head_hash"] == _NEW_HEAD_HASH
    assert stored.payload["new_sequence_number"] == 1
    assert stored.payload["completed_by"] == str(_PRINCIPAL_ID)
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None


@pytest.mark.unit
async def test_complete_seal_republishing_handler_propagates_causation_id() -> None:
    """Optional `causation_id` on the request envelope rides through to the event."""
    store = InMemoryEventStore()
    stream_id = _seal_stream_id()
    await seed_republishing_seal(
        store,
        stream_id=stream_id,
        genesis_event_id=_GENESIS_EVENT_ID,
        start_event_id=_START_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        republishing_started_at=_T1,
        facility_id=_FACILITY_ID,
    )
    causation = UUID("01900000-0000-7000-8000-0000000000cc")
    deps = _build_deps(event_store=store)
    handler = complete_seal_republishing.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )
    events, _ = await store.load("Seal", stream_id)
    assert events[-1].causation_id == causation


@pytest.mark.unit
async def test_complete_seal_republishing_handler_raises_not_found_for_unknown_seal() -> None:
    deps = _build_deps()
    handler = complete_seal_republishing.bind(deps)
    with pytest.raises(SealNotFoundError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_complete_seal_republishing_handler_raises_cannot_complete_when_live() -> None:
    """Single-source: completing a republish on a Live Seal rejects."""
    store = InMemoryEventStore()
    stream_id = _seal_stream_id()
    await seed_live_seal(
        store,
        stream_id=stream_id,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store)
    handler = complete_seal_republishing.bind(deps)
    with pytest.raises(SealCannotCompleteRepublishingError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_complete_seal_republishing_handler_raises_sequence_regression_on_equal_seq() -> None:
    """Monotonicity: a new sequence equal to the prior is rejected at the decider.

    The Republishing seed lands at sequence 0 (no signings yet); requesting
    `new_sequence_number=0` lets the regression guard trip while still
    satisfying the pair-supplied branch.
    """
    store = InMemoryEventStore()
    stream_id = _seal_stream_id()
    await seed_republishing_seal(
        store,
        stream_id=stream_id,
        genesis_event_id=_GENESIS_EVENT_ID,
        start_event_id=_START_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        republishing_started_at=_T1,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store)
    handler = complete_seal_republishing.bind(deps)
    with pytest.raises(SealSequenceNumberRegressionError):
        await handler(
            _command(new_head_hash=_NEW_HEAD_HASH, new_sequence_number=0),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_complete_seal_republishing_handler_raises_value_error_on_pair_imbalance() -> None:
    """The pairing invariant (head + seq together or neither) propagates."""
    store = InMemoryEventStore()
    stream_id = _seal_stream_id()
    await seed_republishing_seal(
        store,
        stream_id=stream_id,
        genesis_event_id=_GENESIS_EVENT_ID,
        start_event_id=_START_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        republishing_started_at=_T1,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store)
    handler = complete_seal_republishing.bind(deps)
    with pytest.raises(ValueError, match="together or omitted together"):
        await handler(
            _command(new_head_hash=_NEW_HEAD_HASH, new_sequence_number=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_complete_seal_republishing_handler_replay_raises_cannot_complete_error() -> None:
    """After a successful complete the Seal is Live; replaying MUST raise."""
    store = InMemoryEventStore()
    stream_id = _seal_stream_id()
    await seed_republishing_seal(
        store,
        stream_id=stream_id,
        genesis_event_id=_GENESIS_EVENT_ID,
        start_event_id=_START_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        republishing_started_at=_T1,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store, ids=[_NEXT_EVENT_ID, _FOLLOWUP_EVENT_ID])
    handler = complete_seal_republishing.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    _, version_after_complete = await store.load("Seal", stream_id)
    assert version_after_complete == 3
    with pytest.raises(SealCannotCompleteRepublishingError):
        await handler(
            _command(new_head_hash="c" * 64, new_sequence_number=2),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version_after_reject = await store.load("Seal", stream_id)
    assert version_after_reject == 3  # untouched after replay rejection


@pytest.mark.unit
async def test_complete_seal_republishing_handler_denies_via_authorize_port() -> None:
    store = InMemoryEventStore()
    stream_id = _seal_stream_id()
    await seed_republishing_seal(
        store,
        stream_id=stream_id,
        genesis_event_id=_GENESIS_EVENT_ID,
        start_event_id=_START_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        republishing_started_at=_T1,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store, deny=True)
    handler = complete_seal_republishing.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_complete_seal_republishing_handler_denied_does_not_write_to_stream() -> None:
    """Authz-denial MUST NOT leave events on the stream."""
    store = InMemoryEventStore()
    stream_id = _seal_stream_id()
    await seed_republishing_seal(
        store,
        stream_id=stream_id,
        genesis_event_id=_GENESIS_EVENT_ID,
        start_event_id=_START_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        republishing_started_at=_T1,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store, deny=True)
    handler = complete_seal_republishing.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Seal", stream_id)
    assert version == 2  # untouched after Initialized + RepublishingStarted seed


@pytest.mark.unit
async def test_complete_seal_republishing_handler_records_completed_by() -> None:
    """The handler injects the request envelope's `principal_id` as
    `completed_by` on the emitted event, regardless of who
    initialized the Seal or started the republish."""
    store = InMemoryEventStore()
    stream_id = _seal_stream_id()
    await seed_republishing_seal(
        store,
        stream_id=stream_id,
        genesis_event_id=_GENESIS_EVENT_ID,
        start_event_id=_START_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_OTHER_PRINCIPAL_ID,
        initialized_at=_T0,
        republishing_started_at=_T1,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store)
    handler = complete_seal_republishing.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Seal", stream_id)
    assert events[-1].payload["completed_by"] == str(_PRINCIPAL_ID)


@pytest.mark.unit
async def test_complete_seal_republishing_handler_raises_value_error_when_no_prior_head() -> None:
    """Republish-only-shape requires a prior signing. The standard seed
    (Initialized + RepublishingStarted, no signings) has head=None, so
    omitting the pair trips the no-prior-head guard at the decider."""
    store = InMemoryEventStore()
    stream_id = _seal_stream_id()
    await seed_republishing_seal(
        store,
        stream_id=stream_id,
        genesis_event_id=_GENESIS_EVENT_ID,
        start_event_id=_START_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        republishing_started_at=_T1,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store)
    handler = complete_seal_republishing.bind(deps)
    with pytest.raises(ValueError, match="current_head_hash is None"):
        await handler(
            _command(new_head_hash=None, new_sequence_number=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
