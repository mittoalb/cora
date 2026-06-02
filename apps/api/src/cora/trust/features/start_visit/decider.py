"""Pure decider for the `StartVisit` command.

Single-source transition: `Arrived -> InProgress`. Strict-not-idempotent.
"""

from datetime import datetime

from cora.trust.aggregates.visit import (
    Visit,
    VisitCannotStartError,
    VisitNotFoundError,
    VisitStarted,
    VisitStatus,
)
from cora.trust.features.start_visit.command import StartVisit

_PERMITTED: tuple[VisitStatus, ...] = (VisitStatus.ARRIVED,)


def decide(
    state: Visit | None,
    command: StartVisit,
    *,
    now: datetime,
) -> list[VisitStarted]:
    """Decide events for starting an Arrived Visit.

    Invariants:
      - State must not be None -> VisitNotFoundError
      - Status must be Arrived -> VisitCannotStartError
    """
    if state is None:
        raise VisitNotFoundError(command.visit_id)
    if state.status not in _PERMITTED:
        raise VisitCannotStartError(
            visit_id=state.id,
            current_status=state.status,
            permitted_sources=_PERMITTED,
        )
    return [VisitStarted(visit_id=state.id, occurred_at=now)]
