"""Unit tests for the `register_actor` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.access.aggregates.actor import (
    Actor,
    ActorAlreadyExistsError,
    ActorKind,
    ActorName,
    InvalidActorNameError,
)
from cora.access.aggregates.actor.events import ActorRegistered
from cora.access.features import register_actor
from cora.access.features.register_actor import RegisterActor

_NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_decide_emits_actor_registered_when_stream_is_empty() -> None:
    new_id = uuid4()
    events = register_actor.decide(
        state=None,
        command=RegisterActor(name="Doga"),
        now=_NOW,
        new_id=new_id,
    )
    assert events == [
        ActorRegistered(actor_id=new_id, name="Doga", occurred_at=_NOW, kind=ActorKind.HUMAN)
    ]


@pytest.mark.unit
def test_decide_trims_name_via_value_object() -> None:
    new_id = uuid4()
    events = register_actor.decide(
        state=None,
        command=RegisterActor(name="  Doga  "),
        now=_NOW,
        new_id=new_id,
    )
    assert events[0].name == "Doga"


@pytest.mark.unit
def test_decide_rejects_invalid_name() -> None:
    with pytest.raises(InvalidActorNameError):
        register_actor.decide(
            state=None,
            command=RegisterActor(name=""),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_existing_state() -> None:
    existing = Actor(id=uuid4(), name=ActorName("Doga"))
    with pytest.raises(ActorAlreadyExistsError) as exc_info:
        register_actor.decide(
            state=existing,
            command=RegisterActor(name="Other"),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.actor_id == existing.id
