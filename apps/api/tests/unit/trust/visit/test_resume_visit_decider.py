"""Decider tests for `resume_visit` (OnHold -> InProgress)."""

import pytest

from cora.trust.aggregates.visit import (
    VisitCannotResumeError,
    VisitNotFoundError,
    VisitResumed,
    VisitStatus,
)
from cora.trust.features.resume_visit import ResumeVisit
from cora.trust.features.resume_visit.decider import decide
from tests.unit.trust.visit._fixtures import NOW, VISIT_ID, make_visit


@pytest.mark.unit
def test_resume_from_on_hold_emits_visit_resumed() -> None:
    events = decide(
        state=make_visit(VisitStatus.ON_HOLD),
        command=ResumeVisit(visit_id=VISIT_ID),
        now=NOW,
    )
    [e] = events
    assert isinstance(e, VisitResumed)
    assert e.visit_id == VISIT_ID
    assert e.occurred_at == NOW


@pytest.mark.unit
def test_resume_raises_not_found_on_empty_state() -> None:
    with pytest.raises(VisitNotFoundError):
        decide(state=None, command=ResumeVisit(visit_id=VISIT_ID), now=NOW)


@pytest.mark.parametrize(
    "current_status",
    [
        VisitStatus.PLANNED,
        VisitStatus.ARRIVED,
        VisitStatus.IN_PROGRESS,
    ],
)
@pytest.mark.unit
def test_resume_rejects_non_on_hold_statuses(current_status: VisitStatus) -> None:
    with pytest.raises(VisitCannotResumeError):
        decide(
            state=make_visit(current_status),
            command=ResumeVisit(visit_id=VISIT_ID),
            now=NOW,
        )
