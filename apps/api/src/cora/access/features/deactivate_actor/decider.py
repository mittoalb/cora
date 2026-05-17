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

## Orthogonality with agent-kind Actors (Phase 8f-a)

`deactivate_actor` accepts ANY Actor regardless of `kind`. For
agent-kind Actors (those co-registered by `define_agent` in the
Agent BC), the Actor's `is_active` flag is ORTHOGONAL to the
Agent aggregate's lifecycle (`Defined / Versioned / Deprecated`).
This is intentional per [[project_agent_bc_design]] cross-BC
review P1-2:

  - `is_active=False` on an agent Actor is a SOFT pause (the
    Actor record exists, can still author historical Decisions,
    but new commands using the principal can be authz-denied at
    the policy layer).
  - `status=Deprecated` on the Agent aggregate is the HARD
    end-of-life signal for an agent kind+version pair.

Future Agent-BC invocation infrastructure (Phase 8f-b's
RunDebrief subscriber and beyond) MUST treat
`is_active=False` AND `kind=agent` as a soft-deprecation: do not
invoke the agent even if its Agent.status is still Versioned.
Decision-existence checks in Decision BC do NOT gate on
`is_active` (the historical fact still holds for Decisions
already written); the deactivation is forward-only and only
affects new commands.
"""

from datetime import datetime

from cora.access.aggregates.actor import (
    Actor,
    ActorAlreadyDeactivatedError,
    ActorDeactivated,
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
