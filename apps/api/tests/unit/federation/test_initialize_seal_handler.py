"""Application-handler tests for the `initialize_seal` slice.

Pins the cross-BC atomic write: every successful `initialize_seal`
call writes ONE `SealInitialized` event on the Seal stream AND ONE
`DecisionRegistered` audit event on the Decision stream via
`EventStore.append_streams`. Mirrors the `register_credential`
precedent (`CredentialRegistered` + `DecisionRegistered`) with one
distinction: the Seal stream id is DETERMINISTIC, derived from
`facility_id` via UUID5, so the handler does not consume an id for
the aggregate (it mints only the audit `decision_id` plus per-event
ids).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.federation.aggregates.seal import SealKeyCollisionError
from cora.federation.aggregates.seal._stream_id import seal_stream_id
from cora.federation.errors import UnauthorizedError
from cora.federation.features import initialize_seal
from cora.federation.features.initialize_seal import InitializeSeal
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports.event_store import ConcurrencyError
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.federation._helpers import seed_live_seal

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_FACILITY_ID = "aps-2bm"
_STREAM_ID = seal_stream_id(_FACILITY_ID)
_DECISION_ID = UUID("01900000-0000-7000-8000-000000fed201")
_SEAL_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed202")
_DECISION_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed203")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000fed299")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000fed2aa")
_ONLINE_KEY_REF = UUID("01900000-0000-7000-8000-00000000c0a1")
_OFFLINE_KEY_REF = UUID("01900000-0000-7000-8000-00000000c0b1")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
    ids: list[UUID] | None = None,
) -> Kernel:
    # initialize_seal consumes 3 ids in order:
    #   1) decision_id (the audit Decision's stream id; aggregate stream
    #      id is deterministic via seal_stream_id(facility_id))
    #   2) seal event_id (one SealInitialized event)
    #   3) decision event_id (one DecisionRegistered event)
    return _build_deps_shared(
        ids=ids if ids is not None else [_DECISION_ID, _SEAL_EVENT_ID, _DECISION_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


def _command(**overrides: object) -> InitializeSeal:
    base: dict[str, object] = {
        "facility_id": _FACILITY_ID,
        "online_key_ref": _ONLINE_KEY_REF,
        "offline_key_ref": _OFFLINE_KEY_REF,
    }
    base.update(overrides)
    return InitializeSeal(**base)  # type: ignore[arg-type]


@pytest.mark.unit
async def test_initialize_seal_handler_returns_deterministic_stream_id() -> None:
    deps = _build_deps()
    handler = initialize_seal.bind(deps)
    result = await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _STREAM_ID


@pytest.mark.unit
async def test_initialize_seal_handler_appends_to_seal_and_decision_streams() -> None:
    """Cross-BC atomic write: SealInitialized on Seal stream AND
    DecisionRegistered on Decision stream via append_streams."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = initialize_seal.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    seal_events, seal_version = await store.load("Seal", _STREAM_ID)
    decision_events, decision_version = await store.load("Decision", _DECISION_ID)

    assert seal_version == 1
    assert decision_version == 1
    assert len(seal_events) == 1
    assert len(decision_events) == 1
    assert seal_events[0].event_type == "SealInitialized"
    assert decision_events[0].event_type == "DecisionRegistered"


@pytest.mark.unit
async def test_initialize_seal_handler_writes_seal_payload_fields() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = initialize_seal.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    seal_events, _ = await store.load("Seal", _STREAM_ID)
    payload = seal_events[0].payload
    assert payload["facility_id"] == _FACILITY_ID
    assert payload["online_key_ref"] == str(_ONLINE_KEY_REF)
    assert payload["offline_key_ref"] == str(_OFFLINE_KEY_REF)
    assert payload["initialized_by_actor_id"] == str(_PRINCIPAL_ID)
    assert payload["occurred_at"] == _NOW.isoformat()


@pytest.mark.unit
async def test_initialize_seal_handler_decision_audit_carries_actor_and_choice() -> None:
    """The co-written DecisionRegistered audit pins actor_id == principal_id,
    context == 'SealInitialized', and choice == facility_id for cross-stream
    correlation against the singleton."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = initialize_seal.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    decision_events, _ = await store.load("Decision", _DECISION_ID)
    payload = decision_events[0].payload
    assert payload["decision_id"] == str(_DECISION_ID)
    assert payload["actor_id"] == str(_PRINCIPAL_ID)
    assert payload["context"] == "SealInitialized"
    assert payload["choice"] == _FACILITY_ID
    assert payload["occurred_at"] == _NOW.isoformat()


@pytest.mark.unit
async def test_initialize_seal_handler_propagates_envelope_to_both_streams() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = initialize_seal.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    seal_events, _ = await store.load("Seal", _STREAM_ID)
    decision_events, _ = await store.load("Decision", _DECISION_ID)
    for events in (seal_events, decision_events):
        stored = events[0]
        assert stored.correlation_id == _CORRELATION_ID
        assert stored.causation_id is None


@pytest.mark.unit
async def test_initialize_seal_handler_propagates_causation_id() -> None:
    """Optional `causation_id` on the request envelope rides through
    to BOTH events written under the cross-BC append_streams."""
    store = InMemoryEventStore()
    causation = UUID("01900000-0000-7000-8000-0000000000cc")
    deps = _build_deps(event_store=store)
    handler = initialize_seal.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )
    seal_events, _ = await store.load("Seal", _STREAM_ID)
    decision_events, _ = await store.load("Decision", _DECISION_ID)
    assert seal_events[0].causation_id == causation
    assert decision_events[0].causation_id == causation


@pytest.mark.unit
async def test_initialize_seal_handler_denies_via_authorize_port() -> None:
    deps = _build_deps(deny=True)
    handler = initialize_seal.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_initialize_seal_handler_denied_does_not_write_either_stream() -> None:
    """Authorize-denial MUST NOT leave events on either stream."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    handler = initialize_seal.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    seal_events, seal_version = await store.load("Seal", _STREAM_ID)
    decision_events, decision_version = await store.load("Decision", _DECISION_ID)
    assert seal_version == 0
    assert decision_version == 0
    assert seal_events == []
    assert decision_events == []


@pytest.mark.unit
async def test_initialize_seal_handler_raises_concurrency_error_when_seal_seeded() -> None:
    """Re-initializing the deterministic-stream Seal singleton raises
    ConcurrencyError at append_streams (expected_version=0 fails against
    a stream already at version 1). The defensive in-decider
    SealAlreadyExistsError guard is unreachable from this handler because
    it always passes state=None to decide; the genesis-collision guard
    is enforced by the event store's optimistic-concurrency check."""
    store = InMemoryEventStore()
    await seed_live_seal(
        store,
        stream_id=_STREAM_ID,
        genesis_event_id=UUID("01900000-0000-7000-8000-000000fed001"),
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=datetime(2026, 5, 30, 10, 0, 0, tzinfo=UTC),
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store)
    handler = initialize_seal.bind(deps)
    with pytest.raises(ConcurrencyError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    # Seeded stream stays at version 1; no second SealInitialized landed.
    _, version = await store.load("Seal", _STREAM_ID)
    assert version == 1


@pytest.mark.unit
async def test_initialize_seal_handler_raises_collision_when_keys_equal() -> None:
    """Decider-layer SealKeyCollisionError bubbles through the handler."""
    shared = uuid4()
    deps = _build_deps()
    handler = initialize_seal.bind(deps)
    with pytest.raises(SealKeyCollisionError):
        await handler(
            _command(online_key_ref=shared, offline_key_ref=shared),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_initialize_seal_handler_collision_does_not_write_either_stream() -> None:
    """Key-collision rejection MUST NOT leave events on either stream."""
    store = InMemoryEventStore()
    shared = uuid4()
    deps = _build_deps(event_store=store)
    handler = initialize_seal.bind(deps)
    with pytest.raises(SealKeyCollisionError):
        await handler(
            _command(online_key_ref=shared, offline_key_ref=shared),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, seal_version = await store.load("Seal", _STREAM_ID)
    _, decision_version = await store.load("Decision", _DECISION_ID)
    assert seal_version == 0
    assert decision_version == 0


@pytest.mark.unit
async def test_initialize_seal_handler_records_initialized_by_actor_id_from_principal() -> None:
    """The handler injects the request envelope's `principal_id` as
    `initialized_by_actor_id`; the command carries no spoofable author."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = initialize_seal.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    seal_events, _ = await store.load("Seal", _STREAM_ID)
    assert seal_events[0].payload["initialized_by_actor_id"] == str(_PRINCIPAL_ID)


@pytest.mark.unit
async def test_initialize_seal_handler_derives_stream_id_from_facility_id() -> None:
    """The returned stream_id matches seal_stream_id(facility_id); two
    distinct facilities mint distinct stream ids."""
    other_facility = "max-iv-balder"
    other_ids = [
        UUID("01900000-0000-7000-8000-000000fed301"),
        UUID("01900000-0000-7000-8000-000000fed302"),
        UUID("01900000-0000-7000-8000-000000fed303"),
    ]
    deps = _build_deps(ids=other_ids)
    handler = initialize_seal.bind(deps)
    result = await handler(
        _command(facility_id=other_facility),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == seal_stream_id(other_facility)
    assert result != _STREAM_ID
