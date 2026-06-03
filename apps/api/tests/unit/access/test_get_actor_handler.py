"""Unit tests for the `get_actor` query handler.

PII vault: the handler returns `ActorView`, a composition of the
Actor aggregate state (id / kind / active) plus the display name
resolved from the `actor_profile` PII vault via
`load_actor_display_name`. Tests pass the InMemoryProfileStore
through the handler so the round-trip register → get exercises
both halves of the vault contract.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.access import UnauthorizedError
from cora.access.aggregates.actor import (
    DELETED_ACTOR_DISPLAY_NAME,
    Actor,
)
from cora.access.features import deactivate_actor, get_actor, register_actor
from cora.access.features.deactivate_actor import DeactivateActor
from cora.access.features.get_actor import GetActor
from cora.access.features.register_actor import RegisterActor
from tests.unit._helpers import RecordingAuthorize, build_deps, make_profile_store

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
async def test_handler_returns_actor_view_for_known_id() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID, _DEACTIVATE_EVENT_ID], now=_NOW)
    profile_store = make_profile_store()
    # Register first so an actor exists (writes the profile vault row).
    await register_actor.bind(deps, profile_store=profile_store)(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_actor.bind(deps, profile_store=profile_store)
    view = await handler(
        GetActor(actor_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.actor == Actor(id=_NEW_ID, active=True)
    assert view.display_name == "Doga"


@pytest.mark.unit
async def test_handler_returns_none_for_unknown_id() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID, _DEACTIVATE_EVENT_ID], now=_NOW)
    handler = get_actor.bind(deps, profile_store=make_profile_store())
    view = await handler(
        GetActor(actor_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert view is None


@pytest.mark.unit
async def test_handler_returns_view_with_is_active_false_after_deactivation() -> None:
    """Round-trip through the write side: register, deactivate, then GET."""
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID, _DEACTIVATE_EVENT_ID], now=_NOW)
    profile_store = make_profile_store()
    await register_actor.bind(deps, profile_store=profile_store)(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await deactivate_actor.bind(deps)(
        DeactivateActor(actor_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_actor.bind(deps, profile_store=profile_store)
    view = await handler(
        GetActor(actor_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.actor.active is False
    assert view.display_name == "Doga"


@pytest.mark.unit
async def test_handler_returns_tombstone_display_name_when_profile_is_erased() -> None:
    """Post-erasure (or never-registered profile) the handler returns
    the tombstone literal from `load_actor_display_name` while still
    exposing the rest of the Actor aggregate state.

    Models the forget_actor end-state: the event stream stays intact
    (pseudonymised per EDPB 01/2025 Example 10) so the actor_id
    reference remains valid; only the display surface degrades."""
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID, _DEACTIVATE_EVENT_ID], now=_NOW)
    profile_store = make_profile_store()
    await register_actor.bind(deps, profile_store=profile_store)(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Simulate post-erasure: pop the profile row via the in-memory
    # adapter's scrub_and_delete (conn is ignored in-memory).
    await profile_store.scrub_and_delete(None, _NEW_ID)

    handler = get_actor.bind(deps, profile_store=profile_store)
    view = await handler(
        GetActor(actor_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.actor.id == _NEW_ID
    assert view.display_name == DELETED_ACTOR_DISPLAY_NAME


@pytest.mark.unit
async def test_handler_authorizes_with_query_name_and_default_conduit() -> None:
    """Query handlers DO call authorize (with AllowAllAuthorize the
    decision is always Allow, but the call site is in place so the
    Trust BC swap is mechanical per handler instead of a sweep that
    risks missing handlers)."""
    tracking = RecordingAuthorize()
    deps = build_deps(
        ids=[_NEW_ID, _EVENT_ID, _DEACTIVATE_EVENT_ID],
        now=_NOW,
        authz=tracking,
    )

    handler = get_actor.bind(deps, profile_store=make_profile_store())
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

    handler = get_actor.bind(deps, profile_store=make_profile_store())
    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            GetActor(actor_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"
