"""Unit tests for the Access evolver."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.access.domain.actor import Actor, ActorName
from cora.access.domain.events import ActorRegistered
from cora.access.domain.evolver import evolve, fold

_NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_evolve_actor_registered_from_empty_state() -> None:
    actor_id = uuid4()
    state = evolve(None, ActorRegistered(actor_id=actor_id, name="Doga", occurred_at=_NOW))
    assert state == Actor(id=actor_id, name=ActorName("Doga"))


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_actor_registered_returns_actor() -> None:
    actor_id = uuid4()
    state = fold([ActorRegistered(actor_id=actor_id, name="Doga", occurred_at=_NOW)])
    assert state == Actor(id=actor_id, name=ActorName("Doga"))


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    actor_id = uuid4()
    events = [ActorRegistered(actor_id=actor_id, name="Doga", occurred_at=_NOW)]
    assert fold(events) == fold(events)


@pytest.mark.unit
def test_decider_and_evolver_round_trip() -> None:
    """The events the decider produces must rebuild the expected state.

    This is the foundational invariant of the decider/evolver pattern:
    decide and evolve must agree on every (state, command) pair. If they
    drift, every command on a saved stream crashes on the next replay.
    Mirror this test for every BC's first decider.
    """
    from cora.access.domain.commands import RegisterActor
    from cora.access.domain.register_actor import register_actor

    new_id = uuid4()
    command = RegisterActor(name="  Doga  ")  # whitespace exercises the VO trim

    events = register_actor(state=None, command=command, now=_NOW, new_id=new_id)
    rebuilt = fold(events)

    assert rebuilt == Actor(id=new_id, name=ActorName("Doga"))
