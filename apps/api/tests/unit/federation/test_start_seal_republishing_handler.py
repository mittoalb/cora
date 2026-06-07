"""Application-handler tests for the `start_seal_republishing` slice.

Covers the authz denial path (no event written), the FSM precondition
rejection on a non-Live source state (Republishing), not-found on an
uninitialized Seal, strict-not-idempotent posture on replay against a
now-Republishing Seal, and the success path's event envelope shape
(correlation_id, causation_id, and the `started_by` denorm
on payload).
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.federation.aggregates.seal import (
    SealCannotStartRepublishingError,
    SealNotFoundError,
)
from cora.federation.aggregates.seal._stream_id import seal_stream_id
from cora.federation.errors import UnauthorizedError
from cora.federation.features import start_seal_republishing
from cora.federation.features.start_seal_republishing import (
    StartSealRepublishing,
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
_FACILITY_ID = "aps-2bm"
_STREAM_ID = seal_stream_id(_FACILITY_ID)
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed001")
_REPUBLISHING_STARTED_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed002")
_NEXT_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed003")
_FOLLOWUP_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed004")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_OTHER_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000088")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


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


def _command(*, reason: str | None = "root rotation drill") -> StartSealRepublishing:
    return StartSealRepublishing(facility_id=_FACILITY_ID, reason=reason)


@pytest.mark.unit
async def test_start_seal_republishing_handler_appends_event_to_live_seal() -> None:
    store = InMemoryEventStore()
    await seed_live_seal(
        store,
        stream_id=_STREAM_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store)
    handler = start_seal_republishing.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Seal", _STREAM_ID)
    assert version == 2
    stored = events[-1]
    assert stored.event_type == "SealRepublishingStarted"
    assert stored.payload["facility_id"] == _FACILITY_ID
    assert stored.payload["started_by"] == str(_PRINCIPAL_ID)
    assert stored.payload["reason"] == "root rotation drill"
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None


@pytest.mark.unit
async def test_start_seal_republishing_handler_propagates_causation_id() -> None:
    """Optional `causation_id` on the request envelope rides through to the event."""
    store = InMemoryEventStore()
    await seed_live_seal(
        store,
        stream_id=_STREAM_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        facility_id=_FACILITY_ID,
    )
    causation = UUID("01900000-0000-7000-8000-0000000000cc")
    deps = _build_deps(event_store=store)
    handler = start_seal_republishing.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )
    events, _ = await store.load("Seal", _STREAM_ID)
    assert events[-1].causation_id == causation


@pytest.mark.unit
async def test_start_seal_republishing_handler_raises_not_found_for_uninitialized_seal() -> None:
    deps = _build_deps()
    handler = start_seal_republishing.bind(deps)
    with pytest.raises(SealNotFoundError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_start_seal_republishing_handler_raises_cannot_start_when_republishing() -> None:
    """A Republishing Seal already has a window in flight; start rejects."""
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
    handler = start_seal_republishing.bind(deps)
    with pytest.raises(SealCannotStartRepublishingError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_start_seal_republishing_handler_replay_raises_cannot_start_error() -> None:
    """After a successful start the Seal is Republishing; replaying MUST raise."""
    store = InMemoryEventStore()
    await seed_live_seal(
        store,
        stream_id=_STREAM_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store, ids=[_NEXT_EVENT_ID, _FOLLOWUP_EVENT_ID])
    handler = start_seal_republishing.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    _, version_after_start = await store.load("Seal", _STREAM_ID)
    assert version_after_start == 2
    with pytest.raises(SealCannotStartRepublishingError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version_after_reject = await store.load("Seal", _STREAM_ID)
    assert version_after_reject == 2  # untouched after replay rejection


@pytest.mark.unit
async def test_start_seal_republishing_handler_denies_via_authorize_port() -> None:
    store = InMemoryEventStore()
    await seed_live_seal(
        store,
        stream_id=_STREAM_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store, deny=True)
    handler = start_seal_republishing.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_start_seal_republishing_handler_denied_does_not_write_to_stream() -> None:
    """Authz-denial MUST NOT leave events on the stream."""
    store = InMemoryEventStore()
    await seed_live_seal(
        store,
        stream_id=_STREAM_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store, deny=True)
    handler = start_seal_republishing.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Seal", _STREAM_ID)
    assert version == 1  # untouched after SealInitialized seed


@pytest.mark.unit
async def test_start_seal_republishing_handler_records_started_by() -> None:
    """The handler injects the request envelope's `principal_id` as
    `started_by` on the emitted event, regardless of who
    initialized the Seal."""
    store = InMemoryEventStore()
    await seed_live_seal(
        store,
        stream_id=_STREAM_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_OTHER_PRINCIPAL_ID,
        initialized_at=_T0,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store)
    handler = start_seal_republishing.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Seal", _STREAM_ID)
    assert events[-1].payload["started_by"] == str(_PRINCIPAL_ID)


@pytest.mark.unit
async def test_start_seal_republishing_handler_event_payload_records_none_reason() -> None:
    """When the operator omits `reason`, the emitted event carries
    None on the payload (round-trip stays clean)."""
    store = InMemoryEventStore()
    await seed_live_seal(
        store,
        stream_id=_STREAM_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_T0,
        facility_id=_FACILITY_ID,
    )
    deps = _build_deps(event_store=store)
    handler = start_seal_republishing.bind(deps)
    await handler(
        _command(reason=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Seal", _STREAM_ID)
    assert version == 2
    assert events[-1].event_type == "SealRepublishingStarted"
    assert events[-1].payload["reason"] is None
