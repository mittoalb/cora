"""Evolver: replay events to reconstruct Visit state.

Mirror of the Campaign / Policy evolvers, generalized for Visit's 8-state
FSM. The terminal `assert_never` case forces pyright (and the runtime) to
error if a new event type is added to `VisitEvent` without a matching
match arm.

Non-genesis events update the existing state's `status` (and
`last_status_reason` when the event carries one), preserving everything
else. `last_status_reason` from VisitHeld / VisitCancelled / VisitAborted
/ VisitVoided is preserved on VisitResumed (audit breadcrumb survives).
"""

from collections.abc import Sequence
from dataclasses import replace
from typing import assert_never

from cora.trust.aggregates.visit.events import (
    VisitAborted,
    VisitArrived,
    VisitCancelled,
    VisitCompleted,
    VisitEvent,
    VisitHeld,
    VisitRegistered,
    VisitResumed,
    VisitStarted,
    VisitVoided,
)
from cora.trust.aggregates.visit.state import Visit, VisitStatus, VisitType


def evolve(state: Visit | None, event: VisitEvent) -> Visit:
    """Apply one event to the current state."""
    match event:
        case VisitRegistered(
            visit_id=visit_id,
            policy_id=policy_id,
            surface_id=surface_id,
            type=type_,
            planned_start_at=planned_start_at,
            planned_end_at=planned_end_at,
            part_of_visit_id=part_of_visit_id,
            external_refs=external_refs,
        ):
            _ = state  # VisitRegistered is genesis; prior state ignored
            return Visit(
                id=visit_id,
                policy_id=policy_id,
                surface_id=surface_id,
                type=VisitType(type_),
                planned_start_at=planned_start_at,
                planned_end_at=planned_end_at,
                part_of_visit_id=part_of_visit_id,
                external_refs=external_refs,
                status=VisitStatus.PLANNED,
                last_status_reason=None,
            )
        case VisitArrived():
            assert state is not None, "VisitArrived requires prior state"
            return replace(state, status=VisitStatus.ARRIVED)
        case VisitStarted():
            assert state is not None, "VisitStarted requires prior state"
            return replace(state, status=VisitStatus.IN_PROGRESS)
        case VisitHeld(reason=reason):
            assert state is not None, "VisitHeld requires prior state"
            return replace(state, status=VisitStatus.ON_HOLD, last_status_reason=reason)
        case VisitResumed():
            assert state is not None, "VisitResumed requires prior state"
            # Preserve last_status_reason audit breadcrumb across resume.
            return replace(state, status=VisitStatus.IN_PROGRESS)
        case VisitCompleted():
            assert state is not None, "VisitCompleted requires prior state"
            return replace(state, status=VisitStatus.COMPLETED)
        case VisitCancelled(reason=reason):
            assert state is not None, "VisitCancelled requires prior state"
            return replace(state, status=VisitStatus.CANCELLED, last_status_reason=reason)
        case VisitAborted(reason=reason):
            assert state is not None, "VisitAborted requires prior state"
            return replace(state, status=VisitStatus.ABORTED, last_status_reason=reason)
        case VisitVoided(reason=reason):
            assert state is not None, "VisitVoided requires prior state"
            return replace(state, status=VisitStatus.VOIDED, last_status_reason=reason)
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[VisitEvent]) -> Visit | None:
    """Replay a stream of events from the empty initial state."""
    state: Visit | None = None
    for event in events:
        state = evolve(state, event)
    return state
