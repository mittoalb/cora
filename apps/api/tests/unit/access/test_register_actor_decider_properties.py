"""Property-based tests for `register_actor.decide` (Access BC).

Complements `test_decider.py` (example-based) with universal claims
across generated inputs. The decider's pure shape

    (state, command, now, new_id) -> list[ActorRegistered]

makes the standard event-sourcing properties mechanical:

  - For state=None and any well-formed command, exactly one event
    is emitted and its fields are exactly the injected ones.
  - For state=Actor, the decider raises ActorAlreadyExistsError
    regardless of any other input (idempotency-as-error).
  - For kind=AGENT, the decider raises InvalidActorKindError before
    name validation (so even invalid names get this error first).

First PBT pass on a production decider, not just a value object.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from cora.access.aggregates.actor import (
    Actor,
    ActorAlreadyExistsError,
    ActorKind,
    ActorRegistered,
    InvalidActorKindError,
)
from cora.access.features import register_actor
from cora.access.features.register_actor import RegisterActor

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

ACTOR_NAME_MAX_LENGTH = 200

_VALID_NAME = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
    min_size=1,
    max_size=ACTOR_NAME_MAX_LENGTH,
)
_NON_AGENT_KIND = st.sampled_from([ActorKind.HUMAN, ActorKind.SERVICE_ACCOUNT])
_ANY_DATETIME = st.datetimes()


def _actor(actor_id: UUID, kind: ActorKind = ActorKind.HUMAN) -> Actor:
    return Actor(id=actor_id, is_active=True, kind=kind)


@pytest.mark.unit
@given(
    name=_VALID_NAME,
    kind=_NON_AGENT_KIND,
    now=_ANY_DATETIME,
    new_id=st.uuids(),
)
def test_register_emits_exactly_one_event_with_injected_fields(
    name: str, kind: ActorKind, now: datetime, new_id: UUID
) -> None:
    """Empty stream + valid command → single ActorRegistered with id=new_id,
    occurred_at=now, kind=command.kind. PII vault: no name on event.
    """
    assume(name == name.strip())  # generator alphabet excludes whitespace
    events = register_actor.decide(
        state=None,
        command=RegisterActor(name=name, kind=kind),
        now=now,
        new_id=new_id,
    )
    assert events == [ActorRegistered(actor_id=new_id, occurred_at=now, kind=kind)]


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    name=_VALID_NAME,
    kind=_NON_AGENT_KIND,
    now=_ANY_DATETIME,
    new_id=st.uuids(),
)
def test_register_on_existing_state_always_raises_already_exists(
    existing_id: UUID, name: str, kind: ActorKind, now: datetime, new_id: UUID
) -> None:
    """Any non-None state → ActorAlreadyExistsError, regardless of command."""
    with pytest.raises(ActorAlreadyExistsError) as exc:
        register_actor.decide(
            state=_actor(existing_id),
            command=RegisterActor(name=name, kind=kind),
            now=now,
            new_id=new_id,
        )
    assert exc.value.actor_id == existing_id


@pytest.mark.unit
@given(
    name=st.text(min_size=0, max_size=ACTOR_NAME_MAX_LENGTH + 50),
    now=_ANY_DATETIME,
    new_id=st.uuids(),
)
def test_register_with_agent_kind_always_raises_invalid_kind(
    name: str, now: datetime, new_id: UUID
) -> None:
    """kind=AGENT is rejected BEFORE name validation, so even invalid
    names produce InvalidActorKindError (not InvalidActorNameError).
    Pins the rejection-order semantics."""
    with pytest.raises(InvalidActorKindError):
        register_actor.decide(
            state=None,
            command=RegisterActor(name=name, kind=ActorKind.AGENT),
            now=now,
            new_id=new_id,
        )


@pytest.mark.unit
@given(
    name=_VALID_NAME,
    kind=_NON_AGENT_KIND,
    now=_ANY_DATETIME,
    new_id=st.uuids(),
)
def test_register_is_pure_same_input_same_output(
    name: str, kind: ActorKind, now: datetime, new_id: UUID
) -> None:
    """Two calls with identical (state, command, now, new_id) return
    identical events (no hidden clock/id leakage)."""
    assume(name == name.strip())
    command = RegisterActor(name=name, kind=kind)
    first = register_actor.decide(state=None, command=command, now=now, new_id=new_id)
    second = register_actor.decide(state=None, command=command, now=now, new_id=new_id)
    assert first == second
