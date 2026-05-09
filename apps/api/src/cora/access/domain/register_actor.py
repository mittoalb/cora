"""Decider for the `RegisterActor` command.

Pure function: given the current Actor state (None for a fresh stream)
and a `RegisterActor` command, returns the events to append. No I/O,
no awaits, no side effects.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports. Keeping them out of the decider's closure
preserves referential transparency for tests.
"""

from datetime import datetime
from uuid import UUID

from cora.access.domain.actor import Actor, ActorAlreadyExistsError, ActorName
from cora.access.domain.commands import RegisterActor
from cora.access.domain.events import ActorRegistered


def register_actor(
    state: Actor | None,
    command: RegisterActor,
    *,
    now: datetime,
    new_id: UUID,
) -> list[ActorRegistered]:
    """Decide the events produced by registering a new actor."""
    if state is not None:
        raise ActorAlreadyExistsError(state.id)
    name = ActorName(command.name)  # validates + trims; raises InvalidActorNameError
    return [
        ActorRegistered(
            actor_id=new_id,
            name=name.value,
            occurred_at=now,
        )
    ]
