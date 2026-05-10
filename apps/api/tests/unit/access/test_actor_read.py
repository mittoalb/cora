"""Unit tests for the Actor aggregate's read repository (`load_actor`).

Exercises fold-on-read against InMemoryEventStore: append events, then
load and assert the rebuilt state matches what the evolver would
produce.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.access.aggregates.actor import (
    Actor,
    ActorName,
    load_actor,
    to_payload,
)
from cora.access.aggregates.actor.events import ActorDeactivated, ActorRegistered
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.ports import NewEvent

_NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)


def _new_event(event: ActorRegistered | ActorDeactivated) -> NewEvent:
    """Wrap a domain event for direct event-store insertion (bypasses handlers)."""
    return NewEvent(
        event_id=uuid4(),
        event_type=type(event).__name__,
        schema_version=1,
        payload=to_payload(event),
        occurred_at=event.occurred_at,
        correlation_id=uuid4(),
        causation_id=None,
        metadata={},
    )


@pytest.mark.unit
async def test_load_actor_returns_none_for_unknown_id() -> None:
    store = InMemoryEventStore()
    actor = await load_actor(store, uuid4())
    assert actor is None


@pytest.mark.unit
async def test_load_actor_rebuilds_active_actor_from_single_event() -> None:
    store = InMemoryEventStore()
    actor_id = uuid4()
    await store.append(
        "Actor",
        actor_id,
        0,
        [_new_event(ActorRegistered(actor_id=actor_id, name="Doga", occurred_at=_NOW))],
    )

    actor = await load_actor(store, actor_id)

    assert actor == Actor(id=actor_id, name=ActorName("Doga"), is_active=True)


@pytest.mark.unit
async def test_load_actor_rebuilds_deactivated_actor_after_replay() -> None:
    store = InMemoryEventStore()
    actor_id = uuid4()
    await store.append(
        "Actor",
        actor_id,
        0,
        [
            _new_event(ActorRegistered(actor_id=actor_id, name="Doga", occurred_at=_NOW)),
            _new_event(ActorDeactivated(actor_id=actor_id, occurred_at=_NOW)),
        ],
    )

    actor = await load_actor(store, actor_id)

    assert actor == Actor(id=actor_id, name=ActorName("Doga"), is_active=False)


@pytest.mark.unit
async def test_load_actor_only_reads_target_stream() -> None:
    """Per-stream isolation: events on a different actor's stream don't leak in."""
    store = InMemoryEventStore()
    target_id = uuid4()
    other_id = uuid4()
    await store.append(
        "Actor",
        other_id,
        0,
        [_new_event(ActorRegistered(actor_id=other_id, name="Other", occurred_at=_NOW))],
    )

    actor = await load_actor(store, target_id)
    assert actor is None
