"""Pure decider for the `DeactivateActor` command.

Update-style decider: receives the rebuilt `Actor` state (folded from
the loaded event stream) and returns the events to append. No I/O.

Invariants:
  - State must not be None (actor must exist) -> ActorNotFoundError
  - State must be active (no double-deactivation)
    -> ActorAlreadyDeactivatedError

Unlike the create-style register_actor decider, no `new_id` is injected
(we operate on an existing aggregate whose id the command already
carries). `now` is still injected from the Clock port at handler time.
"""

from datetime import datetime

from cora.access.aggregates.actor.events import ActorDeactivated
from cora.access.aggregates.actor.state import (
    Actor,
    ActorAlreadyDeactivatedError,
    ActorNotFoundError,
)
from cora.access.features.deactivate_actor.command import DeactivateActor


def decide(
    state: Actor | None,
    command: DeactivateActor,
    *,
    now: datetime,
) -> list[ActorDeactivated]:
    """Decide the events produced by deactivating an existing actor."""
    if state is None:
        raise ActorNotFoundError(command.actor_id)
    if not state.is_active:
        raise ActorAlreadyDeactivatedError(state.id)
    return [ActorDeactivated(actor_id=state.id, occurred_at=now)]
