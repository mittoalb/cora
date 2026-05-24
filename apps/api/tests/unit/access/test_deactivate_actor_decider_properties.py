"""Property-based tests for `deactivate_actor.decide` (Access BC).

Pins the decider's universal behaviour across generated inputs:

  - state=None → ActorNotFoundError, always.
  - state.is_active=False → ActorCannotDeactivateError, always.
  - state.is_active=True → single ActorDeactivated whose actor_id
    is state.id (NOT command.actor_id — a load-bearing distinction
    because the handler loads by command.actor_id but the decider
    emits using the rebuilt state, so a mismatched command/state pair
    silently routes through the state id).
  - Pure: same (state, command, now) → same events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

from cora.access.aggregates.actor import (
    Actor,
    ActorCannotDeactivateError,
    ActorDeactivated,
    ActorKind,
    ActorNotFoundError,
)
from cora.access.features import deactivate_actor
from cora.access.features.deactivate_actor import DeactivateActor

_KIND = st.sampled_from(list(ActorKind))
_DATETIME = st.datetimes()


def _actor(
    actor_id: UUID,
    *,
    is_active: bool = True,
    kind: ActorKind = ActorKind.HUMAN,
) -> Actor:
    return Actor(id=actor_id, is_active=is_active, kind=kind)


@pytest.mark.unit
@given(actor_id=st.uuids(), now=_DATETIME)
def test_deactivate_with_none_state_always_raises_not_found(actor_id: UUID, now: datetime) -> None:
    with pytest.raises(ActorNotFoundError) as exc:
        deactivate_actor.decide(
            state=None,
            command=DeactivateActor(actor_id=actor_id),
            now=now,
        )
    assert exc.value.actor_id == actor_id


@pytest.mark.unit
@given(
    actor_id=st.uuids(),
    command_id=st.uuids(),
    kind=_KIND,
    now=_DATETIME,
)
def test_deactivate_inactive_state_always_raises_already_deactivated(
    actor_id: UUID, command_id: UUID, kind: ActorKind, now: datetime
) -> None:
    """Already-inactive state rejects regardless of which id the
    command targets."""
    with pytest.raises(ActorCannotDeactivateError) as exc:
        deactivate_actor.decide(
            state=_actor(actor_id, is_active=False, kind=kind),
            command=DeactivateActor(actor_id=command_id),
            now=now,
        )
    assert exc.value.actor_id == actor_id


@pytest.mark.unit
@given(
    actor_id=st.uuids(),
    command_id=st.uuids(),
    kind=_KIND,
    now=_DATETIME,
)
def test_deactivate_active_actor_emits_event_with_state_id(
    actor_id: UUID, command_id: UUID, kind: ActorKind, now: datetime
) -> None:
    """Emitted event uses STATE.id, not command.actor_id. Mismatch
    pins the load-bearing source-of-truth invariant for the id.
    """
    events = deactivate_actor.decide(
        state=_actor(actor_id, is_active=True, kind=kind),
        command=DeactivateActor(actor_id=command_id),
        now=now,
    )
    assert events == [ActorDeactivated(actor_id=actor_id, occurred_at=now)]


@pytest.mark.unit
@given(
    actor_id=st.uuids(),
    kind=_KIND,
    now=_DATETIME,
)
def test_deactivate_is_pure_same_input_same_output(
    actor_id: UUID, kind: ActorKind, now: datetime
) -> None:
    state = _actor(actor_id, is_active=True, kind=kind)
    command = DeactivateActor(actor_id=actor_id)
    first = deactivate_actor.decide(state=state, command=command, now=now)
    second = deactivate_actor.decide(state=state, command=command, now=now)
    assert first == second
