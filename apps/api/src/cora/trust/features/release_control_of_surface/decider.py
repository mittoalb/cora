"""Pure decider for the `ReleaseControlOfSurface` command.

Strict-not-idempotent: re-releasing when you are no longer the
holder raises so the audit log never lies about who released.
"""

from datetime import datetime

from cora.trust.aggregates.visit import (
    Visit,
    VisitCannotReleaseControlError,
    VisitNotFoundError,
    VisitSurfaceControlReleased,
)
from cora.trust.features.release_control_of_surface.command import ReleaseControlOfSurface
from cora.trust.features.release_control_of_surface.context import ReleaseControlOfSurfaceContext


def decide(
    state: Visit | None,
    command: ReleaseControlOfSurface,
    *,
    context: ReleaseControlOfSurfaceContext,
    now: datetime,
) -> list[VisitSurfaceControlReleased]:
    """Decide events for releasing a Surface.

    Invariants:
      - State must not be None -> VisitNotFoundError
      - command.surface_id must match state.surface_id
        -> VisitCannotReleaseControlError(reason="surface_mismatch")
      - Active holder must be self
        -> VisitCannotReleaseControlError(reason="not_holder")
    """
    if state is None:
        raise VisitNotFoundError(command.visit_id)
    if state.surface_id != command.surface_id:
        raise VisitCannotReleaseControlError(
            visit_id=state.id,
            surface_id=command.surface_id,
            reason="surface_mismatch",
        )
    active = context.active_holder
    current_holder_id = active.visit_id if active is not None else None
    if current_holder_id != state.id:
        raise VisitCannotReleaseControlError(
            visit_id=state.id,
            surface_id=command.surface_id,
            reason="not_holder",
            current_holder_id=current_holder_id,
        )
    return [
        VisitSurfaceControlReleased(
            visit_id=state.id,
            surface_id=command.surface_id,
            occurred_at=now,
        )
    ]
