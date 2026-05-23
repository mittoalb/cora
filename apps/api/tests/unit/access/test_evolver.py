"""Unit tests for the Actor aggregate's evolver."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.access.aggregates.actor import Actor, ActorKind, evolve, fold
from cora.access.aggregates.actor.events import ActorRegistered
from cora.access.features import register_actor
from cora.access.features.register_actor import RegisterActor

_NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_evolve_actor_registered_from_empty_state() -> None:
    actor_id = uuid4()
    state = evolve(
        None,
        ActorRegistered(actor_id=actor_id, occurred_at=_NOW, kind=ActorKind.HUMAN),
    )
    assert state == Actor(id=actor_id)


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_actor_registered_returns_actor() -> None:
    actor_id = uuid4()
    state = fold([ActorRegistered(actor_id=actor_id, occurred_at=_NOW, kind=ActorKind.HUMAN)])
    assert state == Actor(id=actor_id)


@pytest.mark.unit
def test_decider_and_evolver_round_trip() -> None:
    """The events the decider produces must rebuild the expected state.

    Foundational invariant of the decider/evolver pattern: decide and
    evolve must agree on every (state, command) pair. If they drift,
    every command on a saved stream crashes on the next replay.
    Mirror this test for every BC's first slice.
    """
    new_id = uuid4()
    command = RegisterActor(name="  Doga  ")  # whitespace still exercises the VO trim in decide

    events = register_actor.decide(state=None, command=command, now=_NOW, new_id=new_id)
    rebuilt = fold(events)

    assert rebuilt == Actor(id=new_id)
