"""Unit tests for the `get_actor` query handler."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.access import UnauthorizedError
from cora.access.aggregates.actor import Actor, ActorName
from cora.access.features import deactivate_actor, get_actor, register_actor
from cora.access.features.deactivate_actor import DeactivateActor
from cora.access.features.get_actor import GetActor
from cora.access.features.register_actor import RegisterActor
from cora.infrastructure.ports import (
    Allow,
    AuthzResult,
)
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000000001")
# Some get_actor tests register (and one also deactivates) an actor first
# so a target stream exists; the IdGenerator therefore needs both event
# ids ready alongside the aggregate id.
_EVENT_ID = UUID("01900000-0000-7000-8000-0000000000e1")
_DEACTIVATE_EVENT_ID = UUID("01900000-0000-7000-8000-0000000000e2")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.unit
async def test_handler_returns_actor_for_known_id() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID, _DEACTIVATE_EVENT_ID], now=_NOW)
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
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID, _DEACTIVATE_EVENT_ID], now=_NOW)
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
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID, _DEACTIVATE_EVENT_ID], now=_NOW)
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


class _RecordingAuthorize:
    """Authorize stub that records every call so tests can assert shape."""

    def __init__(self) -> None:
        self.calls: list[tuple[UUID, str, UUID, UUID]] = []

    async def __call__(
        self,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
        surface_id: UUID = UUID(int=0),  # noqa: B008
    ) -> AuthzResult:
        self.calls.append((principal_id, command_name, conduit_id, surface_id))
        return Allow()


@pytest.mark.unit
async def test_handler_authorizes_with_query_name_and_default_conduit() -> None:
    """Phase 2 query handlers DO call authorize (with AllowAllAuthorize the
    decision is always Allow, but the call site is in place so Phase 3
    Trust BC swap is mechanical per handler instead of a sweep that
    risks missing handlers)."""
    tracking = _RecordingAuthorize()
    deps = build_deps(
        ids=[_NEW_ID, _EVENT_ID, _DEACTIVATE_EVENT_ID],
        now=_NOW,
        authorize=tracking,
    )

    handler = get_actor.bind(deps)
    await handler(
        GetActor(actor_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert tracking.calls == [(_PRINCIPAL_ID, "GetActor", UUID(int=0), UUID(int=0))]


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = build_deps(
        ids=[_NEW_ID, _EVENT_ID, _DEACTIVATE_EVENT_ID],
        now=_NOW,
        deny=True,
    )

    handler = get_actor.bind(deps)
    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            GetActor(actor_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"
