"""Pure decider for the `RegisterActor` command.

Pure function: given the current Actor state (None for a fresh stream)
and a `RegisterActor` command, returns the events to append. No I/O,
no awaits, no side effects.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports. Keeping them out of the decider's closure
preserves referential transparency for tests.

Named `decide` (not `register_actor`) because the module is already
`register_actor`; callers read `register_actor.decide(...)`.
"""

from datetime import datetime
from uuid import UUID

from cora.access.aggregates.actor import (
    Actor,
    ActorAlreadyExistsError,
    ActorKind,
    ActorName,
    ActorRegistered,
)
from cora.access.features.register_actor.command import RegisterActor


def decide(
    state: Actor | None,
    command: RegisterActor,
    *,
    now: datetime,
    new_id: UUID,
) -> list[ActorRegistered]:
    """Decide the events produced by registering a new actor.

    `kind` flows from the command (`human` default for backward
    compat with all existing register_actor callers; `service_account`
    opt-in for machine callers per Phase C Iter B-2). Per
    [[project_agent_bc_design]] P0-4: agent-kind Actors MUST NOT be
    minted via this slice — they go through the cross-BC atomic
    write in `define_agent` so the (Agent.id == Actor.id) lock
    holds.
    """
    if state is not None:
        raise ActorAlreadyExistsError(state.id)
    if command.kind == ActorKind.AGENT:
        msg = (
            "register_actor cannot mint kind=agent Actors; agent-kind "
            "Actors come from the cross-BC atomic write in define_agent "
            "per project_agent_bc_design P0-4 (the Agent.id == Actor.id "
            "lock requires the joint write)."
        )
        raise ValueError(msg)
    name = ActorName(command.name)  # validates + trims; raises InvalidActorNameError
    return [
        ActorRegistered(
            actor_id=new_id,
            name=name.value,
            occurred_at=now,
            kind=command.kind,
        )
    ]
