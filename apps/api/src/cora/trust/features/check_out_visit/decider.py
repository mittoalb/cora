"""Pure decider for the `CheckOutVisit` command.

Requires an open presence entry for `actor_id` on the Visit. Does NOT
require any particular `Visit.status` -- check-out from a terminal Visit
is permitted (operator may close lingering presence after the Visit has
already completed). The frozen-replace pattern in the evolver lifts the
entry's `check_out_at` from None to `now`.
"""

from datetime import datetime

from cora.trust.aggregates.visit import (
    Visit,
    VisitActorNotCheckedInError,
    VisitCheckedOut,
    VisitNotFoundError,
)
from cora.trust.features.check_out_visit.command import CheckOutVisit


def decide(
    state: Visit | None,
    command: CheckOutVisit,
    *,
    now: datetime,
) -> list[VisitCheckedOut]:
    """Decide events for checking an actor out of a Visit.

    Invariants:
      - State must not be None -> VisitNotFoundError
      - Actor must have an open presence entry
        -> VisitActorNotCheckedInError
    """
    if state is None:
        raise VisitNotFoundError(command.visit_id)
    open_entry_exists = any(
        e.actor_id == command.actor_id and e.check_out_at is None for e in state.presence_entries
    )
    if not open_entry_exists:
        raise VisitActorNotCheckedInError(visit_id=state.id, actor_id=command.actor_id)
    return [
        VisitCheckedOut(
            visit_id=state.id,
            actor_id=command.actor_id,
            occurred_at=now,
        )
    ]
