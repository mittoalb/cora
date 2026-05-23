"""Unit tests for the `forget_actor` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.access.aggregates.actor import (
    Actor,
    ActorNotFoundError,
    ActorProfileForgotten,
)
from cora.access.features import forget_actor
from cora.access.features.forget_actor import ForgetActor

_NOW = datetime(2026, 5, 23, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_decide_emits_actor_profile_forgotten_for_existing_actor() -> None:
    actor_id = uuid4()
    state = Actor(id=actor_id, is_active=True)

    events = forget_actor.decide(
        state=state,
        command=ForgetActor(actor_id=actor_id),
        now=_NOW,
    )

    assert events == [ActorProfileForgotten(actor_id=actor_id, forgotten_at=_NOW)]


@pytest.mark.unit
def test_decide_emits_event_even_for_already_deactivated_actor() -> None:
    """Erasure is orthogonal to lifecycle: a deactivated actor can
    still have their profile forgotten (and indeed often does, in
    response to a closing-the-loop GDPR request after deactivation).
    """
    actor_id = uuid4()
    state = Actor(id=actor_id, is_active=False)

    events = forget_actor.decide(
        state=state,
        command=ForgetActor(actor_id=actor_id),
        now=_NOW,
    )

    assert events == [ActorProfileForgotten(actor_id=actor_id, forgotten_at=_NOW)]


@pytest.mark.unit
def test_decide_rejects_unknown_actor() -> None:
    actor_id = uuid4()
    with pytest.raises(ActorNotFoundError) as exc_info:
        forget_actor.decide(
            state=None,
            command=ForgetActor(actor_id=actor_id),
            now=_NOW,
        )
    assert exc_info.value.actor_id == actor_id


@pytest.mark.unit
def test_decide_uses_state_id_not_command_id() -> None:
    """Mirrors the deactivate_actor invariant: the emitted event
    uses STATE.id, not command.actor_id. Pins the load-bearing
    source-of-truth invariant for the id."""
    actor_id = uuid4()
    command_id = uuid4()
    state = Actor(id=actor_id, is_active=True)

    events = forget_actor.decide(
        state=state,
        command=ForgetActor(actor_id=command_id),
        now=_NOW,
    )

    assert events[0].actor_id == actor_id
