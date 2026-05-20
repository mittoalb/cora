"""Unit tests for the `register_actor` application handler.

The handler is exercised against in-memory adapters: InMemoryEventStore,
FrozenClock, FixedIdGenerator, and either AllowAllAuthorize or a custom
deny stub. No Postgres, no FastAPI, no async I/O beyond the adapters.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.access import AccessHandlers, UnauthorizedError, wire_access
from cora.access.aggregates.actor import InvalidActorNameError
from cora.access.features import register_actor
from cora.access.features.register_actor import RegisterActor
from cora.infrastructure.memory.event_store import InMemoryEventStore
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000000001")
_EVENT_ID = UUID("01900000-0000-7000-8000-0000000000e1")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.unit
async def test_handler_returns_generated_actor_id() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handler = register_actor.bind(deps)

    result = await handler(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_actor_registered_event_to_store() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = register_actor.bind(deps)

    await handler(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Actor", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "ActorRegistered"
    assert stored.schema_version == 1
    assert stored.payload == {
        "actor_id": str(_NEW_ID),
        "name": "Doga",
        "occurred_at": _NOW.isoformat(),
        "kind": "human",
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "RegisterActor"}
    assert stored.occurred_at == _NOW


@pytest.mark.unit
async def test_handler_trims_actor_name_via_value_object() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = register_actor.bind(deps)

    await handler(
        RegisterActor(name="  Doga  "),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Actor", _NEW_ID)
    assert events[0].payload["name"] == "Doga"


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, deny=True)
    handler = register_actor.bind(deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            RegisterActor(name="Doga"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = register_actor.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            RegisterActor(name="Doga"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Actor", _NEW_ID)
    assert events == []
    assert version == 0


@pytest.mark.unit
async def test_handler_propagates_invalid_actor_name_error() -> None:
    """Domain InvalidActorNameError bubbles unchanged through the handler."""
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handler = register_actor.bind(deps)

    with pytest.raises(InvalidActorNameError):
        await handler(
            RegisterActor(name="   "),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_does_not_append_when_decider_rejects() -> None:
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = register_actor.bind(deps)

    with pytest.raises(InvalidActorNameError):
        await handler(
            RegisterActor(name=""),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Actor", _NEW_ID)
    assert events == []
    assert version == 0


@pytest.mark.unit
async def test_handler_generates_event_id_via_id_generator() -> None:
    """The handler must pull event_ids from the IdGenerator port (one per
    emitted event) so the value persisted on NewEvent.event_id is the
    UUIDv7 the production IdGenerator yields, not a fixed sentinel.

    Verified by injecting a FixedIdGenerator with two known ids — the
    second one (consumed AFTER the aggregate id) must land as the
    appended event's event_id."""
    sentinel_event_id = UUID("01900000-0000-7000-8000-0000000000ee")
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, sentinel_event_id], now=_NOW, event_store=store)
    handler = register_actor.bind(deps)

    await handler(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Actor", _NEW_ID)
    assert events[0].event_id == sentinel_event_id


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    """When the caller passes causation_id, it lands on NewEvent.causation_id.

    Sagas / process managers (future phase) will pass the upstream
    event's id; HTTP/MCP entrypoints leave it None. This test covers
    the explicit-pass path; `test_handler_appends_actor_registered_event_to_store`
    above covers the default-None path.
    """
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = register_actor.bind(deps)

    await handler(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Actor", _NEW_ID)
    assert events[0].causation_id == causation


@pytest.mark.unit
def test_wire_access_returns_handlers_bundle() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handlers = wire_access(deps)
    assert isinstance(handlers, AccessHandlers)
    assert callable(handlers.register_actor)


@pytest.mark.unit
async def test_wired_handler_is_invokable() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handlers = wire_access(deps)
    result = await handlers.register_actor(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_ID


@pytest.mark.unit
async def test_wired_handler_propagates_causation_id_through_full_composition() -> None:
    """End-to-end check that causation_id survives the
    `with_tracing(with_idempotency(bare))` composition chain in wire.py.

    The bare-handler test above (`test_handler_propagates_causation_id_to_appended_event`)
    doesn't exercise the wrappers; this one does, so a regression in
    either decorator's kwarg forwarding would land here.
    """
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handlers = wire_access(deps)

    await handlers.register_actor(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Actor", _NEW_ID)
    assert events[0].causation_id == causation


# ---------- Phase C Iter B-2: kind discriminator ----------


@pytest.mark.unit
async def test_register_actor_persists_service_account_kind() -> None:
    """register_actor(kind=SERVICE_ACCOUNT) emits an ActorRegistered
    event whose kind round-trips through the store as service_account
    (gate-review design#4 follow-up)."""
    from cora.access.aggregates.actor import ActorKind

    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handlers = wire_access(deps)

    await handlers.register_actor(
        RegisterActor(name="ci-bridge", kind=ActorKind.SERVICE_ACCOUNT),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Actor", _NEW_ID)
    assert len(events) == 1
    assert events[0].payload["kind"] == "service_account"


@pytest.mark.unit
async def test_register_actor_default_kind_is_human() -> None:
    """Backward compat: callers that don't set kind get HUMAN."""
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handlers = wire_access(deps)

    await handlers.register_actor(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Actor", _NEW_ID)
    assert events[0].payload["kind"] == "human"


@pytest.mark.unit
async def test_register_actor_rejects_kind_agent_at_decider() -> None:
    """Defense-in-depth: even if a caller bypasses the route's
    closed-set validation, the decider raises `InvalidActorKindError`
    (subclass of ValueError) so the route-layer exception handler maps
    it to 400 via the existing `Invalid*Error` convention (gate-review
    security #3 + impl #2). Agent-kind Actors come from the cross-BC
    atomic write in define_agent only."""
    from cora.access.aggregates.actor import ActorKind, InvalidActorKindError

    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handlers = wire_access(deps)

    with pytest.raises(InvalidActorKindError, match=r"kind='agent'"):
        await handlers.register_actor(
            RegisterActor(name="ghost-agent", kind=ActorKind.AGENT),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
