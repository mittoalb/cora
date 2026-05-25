"""Unit tests for the `deactivate_actor` application handler.

Exercises the load+fold+decide+append flow against InMemoryEventStore.
Covers the update-style handler shape end-to-end including
ConcurrencyError propagation when expected_version is stale.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.access import UnauthorizedError
from cora.access.aggregates.actor import (
    ActorCannotDeactivateError,
    ActorNotFoundError,
)
from cora.access.features import deactivate_actor, register_actor
from cora.access.features.deactivate_actor import DeactivateActor
from cora.access.features.register_actor import RegisterActor
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import (
    ConcurrencyError,
)
from tests.unit._helpers import build_deps, make_profile_store

_NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000000001")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-0000000000e1")
_DEACTIVATE_EVENT_ID = UUID("01900000-0000-7000-8000-0000000000e2")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _register_actor(deps: Kernel) -> UUID:
    """Helper: register an actor and return its id."""
    handler = register_actor.bind(deps, profile_store=make_profile_store())
    return await handler(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.unit
async def test_handler_appends_actor_deactivated_event() -> None:
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_NEW_ID, _REGISTER_EVENT_ID, _DEACTIVATE_EVENT_ID], now=_NOW, event_store=store
    )
    actor_id = await _register_actor(deps)

    handler = deactivate_actor.bind(deps)
    await handler(
        DeactivateActor(actor_id=actor_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Actor", actor_id)
    assert version == 2
    assert events[1].event_type == "ActorDeactivated"
    assert events[1].payload == {
        "actor_id": str(actor_id),
        "occurred_at": _NOW.isoformat(),
    }
    assert events[1].metadata == {"command": "DeactivateActor"}
    assert events[1].correlation_id == _CORRELATION_ID
    assert events[1].causation_id is None
    assert events[1].event_id == _DEACTIVATE_EVENT_ID


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    """Explicit causation_id lands on NewEvent.causation_id of the
    ActorDeactivated event. Mirrors the same test on register_actor;
    the kwarg is wired through the update-style path too so future
    sagas can express "this deactivation was triggered by upstream
    event X" without retrofitting the handler signature."""
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_NEW_ID, _REGISTER_EVENT_ID, _DEACTIVATE_EVENT_ID], now=_NOW, event_store=store
    )
    actor_id = await _register_actor(deps)

    handler = deactivate_actor.bind(deps)
    await handler(
        DeactivateActor(actor_id=actor_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Actor", actor_id)
    assert events[1].causation_id == causation


@pytest.mark.unit
async def test_handler_returns_none() -> None:
    deps = build_deps(ids=[_NEW_ID, _REGISTER_EVENT_ID, _DEACTIVATE_EVENT_ID], now=_NOW)
    actor_id = await _register_actor(deps)

    handler = deactivate_actor.bind(deps)
    result = await handler(
        DeactivateActor(actor_id=actor_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_raises_actor_not_found_for_unknown_id() -> None:
    deps = build_deps(ids=[_NEW_ID, _REGISTER_EVENT_ID, _DEACTIVATE_EVENT_ID], now=_NOW)
    handler = deactivate_actor.bind(deps)

    with pytest.raises(ActorNotFoundError) as exc_info:
        await handler(
            DeactivateActor(actor_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.actor_id is not None


@pytest.mark.unit
async def test_handler_raises_already_deactivated_on_second_call() -> None:
    deps = build_deps(ids=[_NEW_ID, _REGISTER_EVENT_ID, _DEACTIVATE_EVENT_ID], now=_NOW)
    actor_id = await _register_actor(deps)
    handler = deactivate_actor.bind(deps)

    await handler(
        DeactivateActor(actor_id=actor_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    with pytest.raises(ActorCannotDeactivateError):
        await handler(
            DeactivateActor(actor_id=actor_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    # First register normally so the actor exists.
    seed_deps = build_deps(ids=[_NEW_ID, _REGISTER_EVENT_ID, _DEACTIVATE_EVENT_ID], now=_NOW)
    actor_id = await _register_actor(seed_deps)
    # Then point the deactivate handler at the same store but with deny.
    # Even though the auth-deny path never reaches event_id generation,
    # supply enough ids so a regression that bypasses the deny check
    # doesn't fail with a misleading "exhausted" error instead of an
    # UnauthorizedError.
    deny_deps = build_deps(
        ids=[uuid4(), uuid4()],
        now=_NOW,
        deny=True,
        event_store=seed_deps.event_store,
    )
    handler = deactivate_actor.bind(deny_deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            DeactivateActor(actor_id=actor_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # Stream still has only the ActorRegisteredV2 event from setup
    # (V2 = post-PII-vault discriminator string).
    events, version = await deny_deps.event_store.load("Actor", actor_id)
    assert version == 1
    assert events[0].event_type == "ActorRegisteredV2"


@pytest.mark.unit
async def test_handler_propagates_concurrency_error_on_concurrent_write() -> None:
    """Simulate a concurrent write: monkeypatch load() to report a stale
    version so the handler's append at expected_version=stale conflicts
    with the existing event in the stream."""
    store = InMemoryEventStore()
    deps = build_deps(
        ids=[_NEW_ID, _REGISTER_EVENT_ID, _DEACTIVATE_EVENT_ID], now=_NOW, event_store=store
    )
    actor_id = await _register_actor(deps)

    handler = deactivate_actor.bind(deps)

    # Inject a synthetic concurrent-writer race: monkeypatch the store's
    # load to return version=0 even though current_version is 1, so the
    # handler's append at expected_version=0 conflicts with the existing
    # event at version=1.
    original_load = store.load

    async def lying_load(stream_type: str, stream_id: UUID):  # type: ignore[no-untyped-def]
        events, _ = await original_load(stream_type, stream_id)
        return events, 0  # report stale version

    store.load = lying_load  # type: ignore[assignment]

    with pytest.raises(ConcurrencyError):
        await handler(
            DeactivateActor(actor_id=actor_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
