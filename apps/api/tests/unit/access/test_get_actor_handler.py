"""Unit tests for the `get_actor` query handler."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.access.aggregates.actor import Actor, ActorName
from cora.access.features import get_actor, register_actor
from cora.access.features.get_actor import GetActor
from cora.access.features.register_actor import RegisterActor
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    FixedIdGenerator,
    FrozenClock,
)

_NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000000001")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(event_store: InMemoryEventStore | None = None) -> SharedDeps:
    settings = Settings(app_env="test")  # type: ignore[call-arg]
    return SharedDeps(
        settings=settings,
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([_NEW_ID]),
        authorize=AllowAllAuthorize(),
        event_store=event_store or InMemoryEventStore(),
    )


@pytest.mark.unit
async def test_handler_returns_actor_for_known_id() -> None:
    deps = _build_deps()
    # Register first so an actor exists.
    await register_actor.bind(deps)(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_actor.bind(deps)
    actor = await handler(
        GetActor(actor_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert actor == Actor(id=_NEW_ID, name=ActorName("Doga"), is_active=True)


@pytest.mark.unit
async def test_handler_returns_none_for_unknown_id() -> None:
    deps = _build_deps()
    handler = get_actor.bind(deps)
    actor = await handler(
        GetActor(actor_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert actor is None


@pytest.mark.unit
async def test_handler_returns_actor_with_is_active_false_after_deactivation() -> None:
    """Round-trip through the write side: register, deactivate, then GET."""
    from cora.access.features import deactivate_actor
    from cora.access.features.deactivate_actor import DeactivateActor

    deps = _build_deps()
    await register_actor.bind(deps)(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await deactivate_actor.bind(deps)(
        DeactivateActor(actor_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_actor.bind(deps)
    actor = await handler(
        GetActor(actor_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert actor is not None
    assert actor.is_active is False
    assert actor.name == ActorName("Doga")


@pytest.mark.unit
async def test_handler_does_not_authorize_in_phase_2() -> None:
    """Phase-2 query handlers don't call Authorize. Document the behaviour
    so the day Phase 3 adds query authorization, this test breaks loudly
    and the change is intentional."""

    class TrackingAuthorize:
        def __init__(self) -> None:
            self.calls = 0

        async def __call__(self, principal_id: UUID, command_name: str, conduit: str) -> object:
            _ = (principal_id, command_name, conduit)
            self.calls += 1
            from cora.infrastructure.ports import Allow

            return Allow()

    tracking = TrackingAuthorize()
    deps = SharedDeps(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([_NEW_ID]),
        authorize=tracking,  # type: ignore[arg-type]
        event_store=InMemoryEventStore(),
    )

    handler = get_actor.bind(deps)
    await handler(
        GetActor(actor_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert tracking.calls == 0
