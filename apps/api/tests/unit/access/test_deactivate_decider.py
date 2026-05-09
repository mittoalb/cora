"""Unit tests for the `deactivate_actor` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.access.aggregates.actor import (
    Actor,
    ActorAlreadyDeactivatedError,
    ActorDeactivated,
    ActorName,
    ActorNotFoundError,
)
from cora.access.features import deactivate_actor
from cora.access.features.deactivate_actor import DeactivateActor

_NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_decide_emits_actor_deactivated_for_active_actor() -> None:
    actor_id = uuid4()
    state = Actor(id=actor_id, name=ActorName("Doga"), is_active=True)

    events = deactivate_actor.decide(
        state=state,
        command=DeactivateActor(actor_id=actor_id),
        now=_NOW,
    )

    assert events == [ActorDeactivated(actor_id=actor_id, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_rejects_unknown_actor() -> None:
    actor_id = uuid4()
    with pytest.raises(ActorNotFoundError) as exc_info:
        deactivate_actor.decide(
            state=None,
            command=DeactivateActor(actor_id=actor_id),
            now=_NOW,
        )
    assert exc_info.value.actor_id == actor_id


@pytest.mark.unit
def test_decide_rejects_already_deactivated_actor() -> None:
    actor_id = uuid4()
    state = Actor(id=actor_id, name=ActorName("Doga"), is_active=False)

    with pytest.raises(ActorAlreadyDeactivatedError) as exc_info:
        deactivate_actor.decide(
            state=state,
            command=DeactivateActor(actor_id=actor_id),
            now=_NOW,
        )
    assert exc_info.value.actor_id == actor_id


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    actor_id = uuid4()
    state = Actor(id=actor_id, name=ActorName("Doga"), is_active=True)
    command = DeactivateActor(actor_id=actor_id)
    first = deactivate_actor.decide(state=state, command=command, now=_NOW)
    second = deactivate_actor.decide(state=state, command=command, now=_NOW)
    assert first == second
