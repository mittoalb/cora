"""Pure decider for the `CompleteVisit` command.

Multi-source transition: `InProgress | OnHold -> Completed`. Strict-
not-idempotent.
"""

from datetime import datetime

from cora.trust.aggregates.visit import (
    Visit,
    VisitCannotTransitionError,
    VisitCompleted,
    VisitNotFoundError,
    VisitStatus,
)
from cora.trust.features.complete_visit.command import CompleteVisit

_PERMITTED: tuple[VisitStatus, ...] = (VisitStatus.IN_PROGRESS, VisitStatus.ON_HOLD)
_TRANSITION = "complete"


def decide(
    state: Visit | None,
    command: CompleteVisit,
    *,
    now: datetime,
) -> list[VisitCompleted]:
    """Decide events for completing a Visit.

    Invariants:
      - State must not be None -> VisitNotFoundError
      - Status must be InProgress or OnHold -> VisitCannotTransitionError
    """
    if state is None:
        raise VisitNotFoundError(command.visit_id)
    if state.status not in _PERMITTED:
        raise VisitCannotTransitionError(
            visit_id=state.id,
            current_status=state.status,
            requested_transition=_TRANSITION,
            permitted_sources=_PERMITTED,
        )
    return [VisitCompleted(visit_id=state.id, occurred_at=now)]
