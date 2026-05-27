"""Pure decider for the `RegisterVisit` command.

Pure function: given the current Visit state (None for a fresh
stream) and a `RegisterVisit` command, returns the events to append.
No I/O, no awaits, no side effects.

`now` is injected by the application handler.

Genesis idempotency: caller supplies `visit_id`; collision raises
`VisitAlreadyExistsError` (state is None means no prior events on the
stream; non-None means the visit already exists).

Does NOT verify that `policy_id` references an existing Policy, that
`surface_id` references an existing Surface, or that `part_of_visit_id`
references an existing parent Visit. Eventual-consistency stance per
[[project_visit_aggregate_design]] -- the BSS subscriber (Phase iota)
will validate Policy + Surface existence at the subscriber boundary;
partOf cohesion (parent must be on same Surface) and partOf existence
are Phase delta concerns and validated there.
"""

from datetime import datetime

from cora.trust.aggregates.visit import (
    InvalidVisitPlannedPeriodError,
    Visit,
    VisitAlreadyExistsError,
    VisitRegistered,
)
from cora.trust.features.register_visit.command import RegisterVisit


def decide(
    state: Visit | None,
    command: RegisterVisit,
    *,
    now: datetime,
) -> list[VisitRegistered]:
    """Decide the events produced by registering a new visit.

    Invariants:
      - State must be None (caller-supplied visit_id collision guard)
        -> VisitAlreadyExistsError
      - planned_end_at must be strictly after planned_start_at
        -> InvalidVisitPlannedPeriodError
    """
    if state is not None:
        raise VisitAlreadyExistsError(state.id)
    if command.planned_end_at <= command.planned_start_at:
        raise InvalidVisitPlannedPeriodError(
            planned_start_at=command.planned_start_at,
            planned_end_at=command.planned_end_at,
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
            part_of_visit_id=command.part_of_visit_id,
            external_refs=command.external_refs,
        )
    ]
