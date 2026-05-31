"""Pure decider for the `TakeControlOfSurface` command.

Authz check is enforced in the handler via `deps.authz` against
`command.surface_id`; the part_of-descendant relationship is
necessary but NOT sufficient for takeover. A part_of descendant of
the current holder STILL requires the explicit `TakeControlOfSurface`
permission on the target Surface.

Ancestry depth is one-hop; multi-hop chain (grandchild takes from
grandparent) is deferred per `[[project_visit_aggregate_design]]`.
"""

from datetime import datetime

from cora.trust.aggregates.visit import (
    Visit,
    VisitCannotTakeControlError,
    VisitNotFoundError,
    VisitStatus,
    VisitSurfaceControlTaken,
)
from cora.trust.features.take_control_of_surface.command import TakeControlOfSurface
from cora.trust.features.take_control_of_surface.context import TakeControlOfSurfaceContext

_PERMITTED: tuple[VisitStatus, ...] = (
    VisitStatus.ARRIVED,
    VisitStatus.IN_PROGRESS,
    VisitStatus.ON_HOLD,
)


def decide(
    state: Visit | None,
    command: TakeControlOfSurface,
    *,
    context: TakeControlOfSurfaceContext,
    now: datetime,
) -> list[VisitSurfaceControlTaken]:
    """Decide events for taking control of a Surface.

    Invariants:
      - State must not be None -> VisitNotFoundError
      - command.surface_id must match state.surface_id
        -> VisitCannotTakeControlError(reason="surface_mismatch")
      - Status must be Arrived | InProgress | OnHold
        -> VisitCannotTakeControlError(reason="status_not_eligible")
      - Active holder, if present, must be self or part_of parent
        -> VisitCannotTakeControlError(reason="not_descendant")
    """
    if state is None:
        raise VisitNotFoundError(command.visit_id)
    if state.surface_id != command.surface_id:
        raise VisitCannotTakeControlError(
            visit_id=state.id,
            surface_id=command.surface_id,
            reason="surface_mismatch",
        )
    if state.status not in _PERMITTED:
        raise VisitCannotTakeControlError(
            visit_id=state.id,
            surface_id=command.surface_id,
            reason="status_not_eligible",
        )
    active = context.active_holder
    if (
        active is not None
        and active.visit_id != state.id
        and (state.part_of_visit_id is None or state.part_of_visit_id != active.visit_id)
    ):
        raise VisitCannotTakeControlError(
            visit_id=state.id,
            surface_id=command.surface_id,
            reason="not_descendant",
        )
    return [
        VisitSurfaceControlTaken(
            visit_id=state.id,
            surface_id=command.surface_id,
            occurred_at=now,
        )
    ]
