"""Decider tests for `start_visit` (Arrived -> InProgress)."""

import pytest

from cora.trust.aggregates.visit import (
    VisitCannotStartError,
    VisitNotFoundError,
    VisitStarted,
    VisitStatus,
)
from cora.trust.features.start_visit import StartVisit
from cora.trust.features.start_visit.decider import decide
from tests.unit.trust.visit._fixtures import NOW, VISIT_ID, make_visit


@pytest.mark.unit
def test_start_from_arrived_emits_visit_started() -> None:
    events = decide(
        state=make_visit(VisitStatus.ARRIVED),
        command=StartVisit(visit_id=VISIT_ID),
        now=NOW,
    )
    [e] = events
    assert isinstance(e, VisitStarted)
    assert e.visit_id == VISIT_ID
    assert e.occurred_at == NOW


@pytest.mark.unit
def test_start_raises_not_found_on_empty_state() -> None:
    with pytest.raises(VisitNotFoundError):
        decide(state=None, command=StartVisit(visit_id=VISIT_ID), now=NOW)


@pytest.mark.parametrize(
    "current_status",
    [
        VisitStatus.PLANNED,
        VisitStatus.IN_PROGRESS,
        VisitStatus.ON_HOLD,
    ],
)
@pytest.mark.unit
def test_start_rejects_non_arrived_statuses(current_status: VisitStatus) -> None:
    with pytest.raises(VisitCannotStartError) as exc_info:
        decide(
            state=make_visit(current_status),
            command=StartVisit(visit_id=VISIT_ID),
            now=NOW,
        )
    assert exc_info.value.current_status == current_status
