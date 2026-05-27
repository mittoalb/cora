"""Decider tests for `arrive_visit` (Planned -> Arrived; explicit gesture)."""

import pytest

from cora.trust.aggregates.visit import (
    VisitArrived,
    VisitCannotTransitionError,
    VisitNotFoundError,
    VisitStatus,
)
from cora.trust.features.arrive_visit import ArriveVisit
from cora.trust.features.arrive_visit.decider import decide
from tests.unit.trust.visit._fixtures import NOW, VISIT_ID, make_visit


@pytest.mark.unit
def test_arrive_from_planned_emits_visit_arrived() -> None:
    events = decide(
        state=make_visit(VisitStatus.PLANNED),
        command=ArriveVisit(visit_id=VISIT_ID),
        now=NOW,
    )
    assert len(events) == 1
    [e] = events
    assert isinstance(e, VisitArrived)
    assert e.visit_id == VISIT_ID
    assert e.occurred_at == NOW


@pytest.mark.unit
def test_arrive_raises_not_found_on_empty_state() -> None:
    with pytest.raises(VisitNotFoundError):
        decide(state=None, command=ArriveVisit(visit_id=VISIT_ID), now=NOW)


@pytest.mark.parametrize(
    "current_status",
    [
        VisitStatus.ARRIVED,
        VisitStatus.IN_PROGRESS,
        VisitStatus.ON_HOLD,
    ],
)
@pytest.mark.unit
def test_arrive_rejects_non_planned_statuses(current_status: VisitStatus) -> None:
    with pytest.raises(VisitCannotTransitionError) as exc_info:
        decide(
            state=make_visit(current_status),
            command=ArriveVisit(visit_id=VISIT_ID),
            now=NOW,
        )
    assert exc_info.value.current_status == current_status
    assert exc_info.value.requested_transition == "arrive"
    assert exc_info.value.permitted_sources == (VisitStatus.PLANNED,)
