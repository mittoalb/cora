"""Application-handler tests for the `rotate_seal_online_key` slice.

Pins the cross-BC atomic write: every successful `rotate_seal_online_key`
call writes ONE `SealOnlineKeyRotated` event on the Seal stream AND
ONE `DecisionRegistered` audit event on the Decision stream via
`EventStore.append_streams`. Mirrors the `revoke_credential` cross-BC
mid-lifecycle pattern: a security-touching action whose audit emission
is atomic with the domain event.

The Seal stream's expected version on append is the loaded version (1
after genesis), not zero (Seal must already have been initialized).
The Decision stream is fresh (expected version zero).
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.federation.aggregates.seal import (
    SealCannotRotateError,
    SealKeyCollisionError,
    SealNotFoundError,
)
from cora.federation.aggregates.seal._stream_id import seal_stream_id
from cora.federation.errors import UnauthorizedError
from cora.federation.features import rotate_seal_online_key
from cora.federation.features.rotate_seal_online_key import RotateSealOnlineKey
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
_FACILITY_ID = "aps-2bm"
_STREAM_ID = seal_stream_id(_FACILITY_ID)
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed201")
_REPUBLISHING_STARTED_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed202")
_DECISION_ID = UUID("01900000-0000-7000-8000-000000fed205")
_SEAL_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed206")
_DECISION_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed207")
_FOLLOWUP_DECISION_ID = UUID("01900000-0000-7000-8000-000000fed208")
_FOLLOWUP_SEAL_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed209")
_FOLLOWUP_DECISION_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed20a")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_OTHER_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000088")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CURRENT_ONLINE_KEY = UUID("01900000-0000-7000-8000-00000000c0a1")
_OFFLINE_KEY = UUID("01900000-0000-7000-8000-00000000c0b1")
_NEW_ONLINE_KEY = UUID("01900000-0000-7000-8000-00000000c0a2")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
    ids: list[UUID] | None = None,
) -> Kernel:
    # rotate_seal_online_key consumes 3 ids per successful call:
    #   1) decision_id (fresh Decision stream id)
    #   2) seal event_id (one SealOnlineKeyRotated event)
    #   3) decision event_id (one DecisionRegistered event)
    return _build_deps_shared(
        ids=(ids if ids is not None else [_DECISION_ID, _SEAL_EVENT_ID, _DECISION_EVENT_ID]),
        now=_T2,
        event_store=event_store,
        deny=deny,
    )


def _command(new_online_key_ref: UUID = _NEW_ONLINE_KEY) -> RotateSealOnlineKey:
    return RotateSealOnlineKey(
        facility_id=_FACILITY_ID,
        new_online_key_ref=new_online_key_ref,
    )


async def _seed_live(store: InMemoryEventStore) -> None:
    await seed_live_seal(
        store,
        stream_id=_STREAM_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        facility_id=_FACILITY_ID,
        online_key_ref=_CURRENT_ONLINE_KEY,
        offline_key_ref=_OFFLINE_KEY,
    )


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_appends_event_from_live() -> None:
    store = InMemoryEventStore()
    await _seed_live(store)
    deps = _build_deps(event_store=store)
    handler = rotate_seal_online_key.bind(deps)

    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Seal", _STREAM_ID)
    assert version == 2
    transition = events[-1]
    assert transition.event_type == "SealOnlineKeyRotated"
    assert transition.payload["facility_id"] == _FACILITY_ID
    assert transition.payload["new_online_key_ref"] == str(_NEW_ONLINE_KEY)
    assert transition.payload["rotated_by_actor_id"] == str(_PRINCIPAL_ID)
    assert transition.correlation_id == _CORRELATION_ID
    assert transition.causation_id is None


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_appends_to_both_seal_and_decision_streams() -> None:
    """Cross-BC atomic write: SealOnlineKeyRotated on Seal stream AND
    DecisionRegistered on Decision stream via append_streams."""
    store = InMemoryEventStore()
    await _seed_live(store)
    deps = _build_deps(event_store=store)
    handler = rotate_seal_online_key.bind(deps)

    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    seal_events, seal_version = await store.load("Seal", _STREAM_ID)
    decision_events, decision_version = await store.load("Decision", _DECISION_ID)

    assert seal_version == 2  # genesis + rotate
    assert decision_version == 1  # fresh Decision stream
    assert len(seal_events) == 2
    assert len(decision_events) == 1
    assert seal_events[-1].event_type == "SealOnlineKeyRotated"
    assert decision_events[0].event_type == "DecisionRegistered"


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_decision_audit_carries_actor_and_choice() -> None:
    """The co-written DecisionRegistered audit pins actor_id == principal_id,
    context == 'SealOnlineKeyRotated', and choice == facility_id for
    cross-stream correlation."""
    store = InMemoryEventStore()
    await _seed_live(store)
    deps = _build_deps(event_store=store)
    handler = rotate_seal_online_key.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    decision_events, _ = await store.load("Decision", _DECISION_ID)
    payload = decision_events[0].payload
    assert payload["decision_id"] == str(_DECISION_ID)
    assert payload["actor_id"] == str(_PRINCIPAL_ID)
    assert payload["context"] == "SealOnlineKeyRotated"
    assert payload["choice"] == _FACILITY_ID
    assert payload["occurred_at"] == _T2.isoformat()


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_propagates_envelope_to_both_streams() -> None:
    store = InMemoryEventStore()
    await _seed_live(store)
    deps = _build_deps(event_store=store)
    handler = rotate_seal_online_key.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    seal_events, _ = await store.load("Seal", _STREAM_ID)
    decision_events, _ = await store.load("Decision", _DECISION_ID)
    seal_rotate = seal_events[-1]
    decision_audit = decision_events[0]
    assert seal_rotate.correlation_id == _CORRELATION_ID
    assert seal_rotate.causation_id is None
    assert decision_audit.correlation_id == _CORRELATION_ID
    assert decision_audit.causation_id is None


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_propagates_causation_id() -> None:
    store = InMemoryEventStore()
    await _seed_live(store)
    deps = _build_deps(event_store=store)
    handler = rotate_seal_online_key.bind(deps)

    causation_id = UUID("01900000-0000-7000-8000-0000000000cc")
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation_id,
    )

    seal_events, _ = await store.load("Seal", _STREAM_ID)
    decision_events, _ = await store.load("Decision", _DECISION_ID)
    assert seal_events[-1].causation_id == causation_id
    assert decision_events[0].causation_id == causation_id


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_raises_not_found_for_uninitialized_seal() -> None:
    deps = _build_deps(event_store=InMemoryEventStore())
    handler = rotate_seal_online_key.bind(deps)
    with pytest.raises(SealNotFoundError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_raises_cannot_rotate_when_republishing() -> None:
    """Strict-not-idempotent: rotating against a Republishing Seal raises."""
    store = InMemoryEventStore()
    await seed_republishing_seal(
        store,
        stream_id=_STREAM_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        start_event_id=_REPUBLISHING_STARTED_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        republishing_started_at=_T1,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store)
    handler = rotate_seal_online_key.bind(deps)
    with pytest.raises(SealCannotRotateError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Seal", _STREAM_ID)
    assert version == 2  # untouched seed (Initialized + RepublishingStarted)


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_raises_cannot_rotate_on_noop_rotation() -> None:
    """Strict-not-idempotent: re-rotating to the same online ref raises."""
    store = InMemoryEventStore()
    await _seed_live(store)
    deps = _build_deps(event_store=store)
    handler = rotate_seal_online_key.bind(deps)
    with pytest.raises(SealCannotRotateError):
        await handler(
            _command(new_online_key_ref=_CURRENT_ONLINE_KEY),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Seal", _STREAM_ID)
    assert version == 1  # untouched seed


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_raises_collision_when_ref_equals_offline() -> None:
    """Key-separation invariant: rotating to a ref equal to offline raises."""
    store = InMemoryEventStore()
    await _seed_live(store)
    deps = _build_deps(event_store=store)
    handler = rotate_seal_online_key.bind(deps)
    with pytest.raises(SealKeyCollisionError) as exc_info:
        await handler(
            _command(new_online_key_ref=_OFFLINE_KEY),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.shared_key_ref == _OFFLINE_KEY
    _, version = await store.load("Seal", _STREAM_ID)
    assert version == 1  # untouched seed


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_strict_not_idempotent_raises_on_re_rotate() -> None:
    """After a successful rotation the slot holds the new ref; re-rotating to
    that same ref MUST raise (no-op rejected) and MUST NOT write to either stream."""
    store = InMemoryEventStore()
    await _seed_live(store)
    deps = _build_deps(event_store=store)
    handler = rotate_seal_online_key.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    _, version_after_first = await store.load("Seal", _STREAM_ID)
    assert version_after_first == 2

    deps2 = _build_deps(
        event_store=store,
        ids=[
            _FOLLOWUP_DECISION_ID,
            _FOLLOWUP_SEAL_EVENT_ID,
            _FOLLOWUP_DECISION_EVENT_ID,
        ],
    )
    handler2 = rotate_seal_online_key.bind(deps2)
    with pytest.raises(SealCannotRotateError):
        await handler2(
            _command(new_online_key_ref=_NEW_ONLINE_KEY),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version_after_reject = await store.load("Seal", _STREAM_ID)
    assert version_after_reject == 2  # untouched after re-rotate rejection
    _, followup_decision_version = await store.load("Decision", _FOLLOWUP_DECISION_ID)
    assert followup_decision_version == 0  # no second Decision stream landed


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_denies_via_authorize_port() -> None:
    store = InMemoryEventStore()
    await _seed_live(store)
    deps = _build_deps(event_store=store, deny=True)
    handler = rotate_seal_online_key.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_denied_does_not_write_either_stream() -> None:
    """Authorize-denial MUST NOT leave events on EITHER stream."""
    store = InMemoryEventStore()
    await _seed_live(store)
    deps = _build_deps(event_store=store, deny=True)
    handler = rotate_seal_online_key.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, seal_version = await store.load("Seal", _STREAM_ID)
    decision_events, decision_version = await store.load("Decision", _DECISION_ID)
    assert seal_version == 1  # untouched: just the SealInitialized seed
    assert decision_version == 0
    assert decision_events == []


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_records_principal_as_rotated_by_actor_id() -> None:
    """The handler injects the request envelope's `principal_id` as
    `rotated_by_actor_id` on the emitted event (audit anchor for the
    operator gesture), regardless of who initialized the seal."""
    store = InMemoryEventStore()
    # Seed Initialized BY a different actor; the rotator should still be
    # recorded as the invoking principal.
    await seed_live_seal(
        store,
        stream_id=_STREAM_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_OTHER_PRINCIPAL_ID,
        initialized_at=_T0,
        facility_id=_FACILITY_ID,
        online_key_ref=_CURRENT_ONLINE_KEY,
        offline_key_ref=_OFFLINE_KEY,
    )
    deps = _build_deps(event_store=store)
    handler = rotate_seal_online_key.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Seal", _STREAM_ID)
    assert events[-1].payload["rotated_by_actor_id"] == str(_PRINCIPAL_ID)
    decision_events, _ = await store.load("Decision", _DECISION_ID)
    assert decision_events[0].payload["actor_id"] == str(_PRINCIPAL_ID)


@pytest.mark.unit
async def test_rotate_seal_online_key_handler_targets_deterministic_stream_id() -> None:
    """The handler derives the stream UUID via `seal_stream_id(facility_id)`;
    the rotation event lands on that same deterministic stream."""
    store = InMemoryEventStore()
    await _seed_live(store)
    deps = _build_deps(event_store=store)
    handler = rotate_seal_online_key.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    expected_stream_id = seal_stream_id(_FACILITY_ID)
    events, version = await store.load("Seal", expected_stream_id)
    assert version == 2
    assert events[-1].event_type == "SealOnlineKeyRotated"
