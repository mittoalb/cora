"""Unit tests for the `forget_actor` application handler.

Exercises the load + fold + decide + scrub-then-append flow against
the in-memory adapters (no Postgres transaction; both adapters
tolerate `conn=None`). The Postgres-side single-transaction
atomicity is covered separately in
`tests/integration/test_forget_actor_handler_postgres.py`.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.access import UnauthorizedError
from cora.access.aggregates.actor import (
    DELETED_ACTOR_DISPLAY_NAME,
    ActorNotFoundError,
    load_actor_display_name,
)
from cora.access.features import forget_actor, register_actor
from cora.access.features.forget_actor import ForgetActor
from cora.access.features.register_actor import RegisterActor
from cora.infrastructure.memory.event_store import InMemoryEventStore
from tests.unit._helpers import build_deps, make_profile_store

_NOW = datetime(2026, 5, 23, 12, 0, 0, tzinfo=UTC)
_ACTOR_ID = UUID("01900000-0000-7000-8000-00000000beef")
_REGISTER_EVENT_ID = UUID("01900000-0000-7000-8000-00000000eee1")
_FORGET_EVENT_ID = UUID("01900000-0000-7000-8000-00000000eef2")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.unit
async def test_handler_scrubs_profile_and_appends_audit_event() -> None:
    """End-to-end happy path: register an actor (writes the vault),
    forget the actor (scrubs the vault row + appends
    ActorProfileForgotten). Verified by reading both back."""
    store = InMemoryEventStore()
    profile_store = make_profile_store()
    deps = build_deps(
        ids=[_ACTOR_ID, _REGISTER_EVENT_ID, _FORGET_EVENT_ID],
        now=_NOW,
        event_store=store,
        profile_store=profile_store,
    )

    await register_actor.bind(deps, profile_store=profile_store)(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Sanity: vault populated by register.
    assert (await profile_store.get(_ACTOR_ID)) is not None

    handler = forget_actor.bind(deps)
    result = await handler(
        ForgetActor(actor_id=_ACTOR_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result is None
    # Vault row erased.
    assert (await profile_store.get(_ACTOR_ID)) is None
    # Display-fallback helper now returns the tombstone literal.
    assert (await load_actor_display_name(profile_store, _ACTOR_ID)) == DELETED_ACTOR_DISPLAY_NAME

    # Audit event landed on the actor stream.
    events, version = await store.load("Actor", _ACTOR_ID)
    assert version == 2
    assert [e.event_type for e in events] == [
        "ActorRegisteredV2",
        "ActorProfileForgotten",
    ]
    forgotten = events[1]
    assert forgotten.payload == {
        "actor_id": str(_ACTOR_ID),
        "forgotten_at": _NOW.isoformat(),
    }
    assert forgotten.metadata == {"command": "ForgetActor"}
    assert forgotten.correlation_id == _CORRELATION_ID
    assert forgotten.causation_id is None
    assert forgotten.event_id == _FORGET_EVENT_ID
    assert forgotten.principal_id == _PRINCIPAL_ID


@pytest.mark.unit
async def test_handler_raises_actor_not_found_for_unknown_id() -> None:
    """No prior register -> ActorNotFoundError before any I/O."""
    deps = build_deps(ids=[_FORGET_EVENT_ID], now=_NOW)
    handler = forget_actor.bind(deps)
    unknown = UUID("01900000-0000-7000-8000-0000000000ff")

    with pytest.raises(ActorNotFoundError) as exc_info:
        await handler(
            ForgetActor(actor_id=unknown),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    assert exc_info.value.actor_id == unknown


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny_and_leaves_vault_intact() -> None:
    """Deny gates the whole write — neither vault scrub nor event
    append fires."""
    # Use one shared profile_store / event_store across the seed
    # and the deny build so the deny path operates on the seeded
    # actor.
    store = InMemoryEventStore()
    profile_store = make_profile_store()
    seed_deps = build_deps(
        ids=[_ACTOR_ID, _REGISTER_EVENT_ID, _FORGET_EVENT_ID],
        now=_NOW,
        event_store=store,
        profile_store=profile_store,
    )
    await register_actor.bind(seed_deps, profile_store=profile_store)(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    deny_deps = build_deps(
        ids=[_FORGET_EVENT_ID],
        now=_NOW,
        event_store=store,
        profile_store=profile_store,
        deny=True,
    )
    handler = forget_actor.bind(deny_deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            ForgetActor(actor_id=_ACTOR_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"

    # Vault row preserved; only the one register event on the stream.
    assert (await profile_store.get(_ACTOR_ID)) is not None
    events, version = await store.load("Actor", _ACTOR_ID)
    assert version == 1
    assert events[0].event_type == "ActorRegisteredV2"


@pytest.mark.unit
async def test_handler_emits_second_event_on_repeat_call() -> None:
    """Idempotency at the AUDIT level: a repeat ForgetActor against
    an already-forgotten actor emits a second ActorProfileForgotten
    event (records "operator clicked forget twice"). The vault
    scrub is a no-op on the missing row. The idempotency-wrap at
    wire.py is the layer that short-circuits double-clicks at the
    HTTP layer; the bare handler does not."""
    store = InMemoryEventStore()
    profile_store = make_profile_store()
    deps = build_deps(
        ids=[
            _ACTOR_ID,
            _REGISTER_EVENT_ID,
            _FORGET_EVENT_ID,
            UUID("01900000-0000-7000-8000-00000000eef3"),
        ],
        now=_NOW,
        event_store=store,
        profile_store=profile_store,
    )

    await register_actor.bind(deps, profile_store=profile_store)(
        RegisterActor(name="Doga"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = forget_actor.bind(deps)
    await handler(
        ForgetActor(actor_id=_ACTOR_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Second call: vault already erased, but the audit event lands
    # again so the operator-action history is faithful.
    await handler(
        ForgetActor(actor_id=_ACTOR_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Actor", _ACTOR_ID)
    assert version == 3
    assert [e.event_type for e in events] == [
        "ActorRegisteredV2",
        "ActorProfileForgotten",
        "ActorProfileForgotten",
    ]
    assert (await profile_store.get(_ACTOR_ID)) is None
