"""Unit tests for the `register_actor` decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.access.domain.actor import (
    Actor,
    ActorAlreadyExistsError,
    ActorName,
    InvalidActorNameError,
)
from cora.access.domain.commands import RegisterActor
from cora.access.domain.events import ActorRegistered
from cora.access.domain.register_actor import register_actor

_NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_register_actor_emits_actor_registered_when_stream_is_empty() -> None:
    new_id = uuid4()
    events = register_actor(
        state=None,
        command=RegisterActor(name="Doga"),
        now=_NOW,
        new_id=new_id,
    )
    assert events == [ActorRegistered(actor_id=new_id, name="Doga", occurred_at=_NOW)]


@pytest.mark.unit
def test_register_actor_trims_name_via_value_object() -> None:
    new_id = uuid4()
    events = register_actor(
        state=None,
        command=RegisterActor(name="  Doga  "),
        now=_NOW,
        new_id=new_id,
    )
    assert events[0].name == "Doga"


@pytest.mark.unit
def test_register_actor_rejects_invalid_name() -> None:
    with pytest.raises(InvalidActorNameError):
        register_actor(
            state=None,
            command=RegisterActor(name=""),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_register_actor_rejects_existing_state() -> None:
    existing = Actor(id=uuid4(), name=ActorName("Doga"))
    with pytest.raises(ActorAlreadyExistsError) as exc_info:
        register_actor(
            state=existing,
            command=RegisterActor(name="Other"),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.actor_id == existing.id


@pytest.mark.unit
def test_register_actor_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    command = RegisterActor(name="Doga")
    first = register_actor(state=None, command=command, now=_NOW, new_id=new_id)
    second = register_actor(state=None, command=command, now=_NOW, new_id=new_id)
    assert first == second
