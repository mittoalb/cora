"""Pure decider for the `RegisterVisit` command.

Pure function: given the current Visit state (None for a fresh
stream), a `RegisterVisit` command, and a `RegisterVisitContext`
preloaded snapshot, returns the events to append. No I/O, no awaits,
no side effects.

`now` is injected by the application handler.

Genesis idempotency: caller supplies `visit_id`; collision raises
`VisitAlreadyExistsError` (state is None means no prior events on the
stream; non-None means the visit already exists).

PartOf cohesion: when the command sets `parent_id`, the
handler preloads the parent Visit via `context.parent_visit`. The
decider then enforces:
  - `VisitParentNotFoundError` if `command.parent_id` is set
    but the parent stream is empty (`context.parent_visit is None`).
  - `VisitParentMismatchedSurfaceError` if `parent.surface_id` differs
    from the child's `surface_id`.

Still does NOT verify that `policy_id` references an existing Policy
or that `surface_id` references an existing Surface. Eventual-
consistency stance per [[project_visit_aggregate_design]] -- the BSS
subscriber will validate Policy + Surface existence at the subscriber
boundary.
"""

from datetime import datetime

from cora.trust.aggregates.visit import (
    InvalidVisitPlannedPeriodError,
    Visit,
    VisitAlreadyExistsError,
    VisitParentMismatchedSurfaceError,
    VisitParentNotFoundError,
    VisitRegistered,
)
from cora.trust.features.register_visit.command import RegisterVisit
from cora.trust.features.register_visit.context import RegisterVisitContext


def decide(
    state: Visit | None,
    command: RegisterVisit,
    *,
    context: RegisterVisitContext,
    now: datetime,
) -> list[VisitRegistered]:
    """Decide the events produced by registering a new visit.

    Invariants:
      - State must be None (caller-supplied visit_id collision guard)
        -> VisitAlreadyExistsError
      - planned_end_at must be strictly after planned_start_at
        -> InvalidVisitPlannedPeriodError
      - If parent_id set, parent must exist
        -> VisitParentNotFoundError
      - If parent exists, parent.surface_id must match command.surface_id
        -> VisitParentMismatchedSurfaceError
    """
    if state is not None:
        raise VisitAlreadyExistsError(state.id)
    if command.planned_end_at <= command.planned_start_at:
        raise InvalidVisitPlannedPeriodError(
            planned_start_at=command.planned_start_at,
            planned_end_at=command.planned_end_at,
        )
    if command.parent_id is not None:
        if context.parent_visit is None:
            raise VisitParentNotFoundError(
                visit_id=command.visit_id,
                parent_id=command.parent_id,
            )
        if context.parent_visit.surface_id != command.surface_id:
            raise VisitParentMismatchedSurfaceError(
                visit_id=command.visit_id,
                child_surface_id=command.surface_id,
                parent_id=command.parent_id,
                parent_surface_id=context.parent_visit.surface_id,
            )
    return [
        VisitRegistered(
            visit_id=command.visit_id,
            policy_id=command.policy_id,
            surface_id=command.surface_id,
            type=command.type.value,
            planned_start_at=command.planned_start_at,
            planned_end_at=command.planned_end_at,
            occurred_at=now,
            parent_id=command.parent_id,
            external_refs=command.external_refs,
        )
    ]
