"""Pure decider for the `ForgetActor` PII-erasure command.

Update-style decider: receives the rebuilt `Actor` state (folded
from the loaded event stream) and returns the events to append. No
I/O. The actual `ProfileStore.scrub_and_delete` call happens in the
handler inside the same transaction as the event append.

Invariants:
  - State must not be None (actor must exist) -> ActorNotFoundError

Idempotency: a repeated `ForgetActor` call on an already-forgotten
actor still emits a second `ActorProfileForgotten` event. That is
intentional per the design memo's "Failure modes" section: each
audit event records a distinct operator action ("operator clicked
forget twice"), and the side-table `scrub_and_delete` is a no-op
on the second call. The decider deliberately does NOT inspect the
event log for prior erasures — the existence of the actor
(stream non-empty) is the only precondition.
"""

from datetime import datetime

from cora.access.aggregates.actor import (
    Actor,
    ActorNotFoundError,
    ActorProfileForgotten,
)
from cora.access.features.forget_actor.command import ForgetActor


def decide(
    state: Actor | None,
    command: ForgetActor,
    *,
    now: datetime,
) -> list[ActorProfileForgotten]:
    """Decide the events produced by forgetting an actor's PII."""
    if state is None:
        raise ActorNotFoundError(command.actor_id)
    return [ActorProfileForgotten(actor_id=state.id, occurred_at=now)]
