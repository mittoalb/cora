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
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.memory.idempotency import InMemoryIdempotencyStore
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    AuthzResult,
    Deny,
    FixedIdGenerator,
    FrozenClock,
)

_NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000000001")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


class DenyAllAuthorize:
    """Authorize stub that denies every command."""

    async def __call__(
        self,
        principal_id: UUID,
        command_name: str,
        conduit: str,
    ) -> AuthzResult:
        _ = (principal_id, command_name, conduit)
        return Deny(reason="denied for test")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> SharedDeps:
    settings = Settings(app_env="test")  # type: ignore[call-arg]
    return SharedDeps(
        settings=settings,
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([_NEW_ID]),
        authorize=DenyAllAuthorize() if deny else AllowAllAuthorize(),
        event_store=event_store or InMemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
    )


@pytest.mark.unit
async def test_handler_returns_generated_actor_id() -> None:
    deps = _build_deps()
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
    deps = _build_deps(event_store=store)
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
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.metadata == {"command": "RegisterActor"}
    assert stored.occurred_at == _NOW


@pytest.mark.unit
async def test_handler_trims_actor_name_via_value_object() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
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
    deps = _build_deps(deny=True)
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
    deps = _build_deps(event_store=store, deny=True)
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
    deps = _build_deps()
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
    deps = _build_deps(event_store=store)
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
def test_wire_access_returns_handlers_bundle() -> None:
    deps = _build_deps()
    handlers = wire_access(deps)
    assert isinstance(handlers, AccessHandlers)
    assert callable(handlers.register_actor)


@pytest.mark.unit
async def test_wired_handler_is_invokable() -> None:
    deps = _build_deps()
    handlers = wire_access(deps)
    result = await handlers.register_actor(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_ID
