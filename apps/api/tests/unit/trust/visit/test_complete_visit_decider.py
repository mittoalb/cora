"""Decider tests for `complete_visit` (InProgress | OnHold -> Completed)."""

import pytest

from cora.trust.aggregates.visit import (
    VisitCannotCompleteError,
    VisitCompleted,
    VisitNotFoundError,
    VisitStatus,
)
from cora.trust.features.complete_visit import CompleteVisit
from cora.trust.features.complete_visit.decider import decide
from tests.unit.trust.visit._fixtures import NOW, VISIT_ID, make_visit


@pytest.mark.parametrize(
    "from_status",
    [VisitStatus.IN_PROGRESS, VisitStatus.ON_HOLD],
)
@pytest.mark.unit
def test_complete_from_active_statuses_emits_visit_completed(from_status: VisitStatus) -> None:
    events = decide(
        state=make_visit(from_status),
        command=CompleteVisit(visit_id=VISIT_ID),
        now=NOW,
    )
    [e] = events
    assert isinstance(e, VisitCompleted)
    assert e.occurred_at == NOW


@pytest.mark.unit
def test_complete_raises_not_found_on_empty_state() -> None:
    with pytest.raises(VisitNotFoundError):
        decide(state=None, command=CompleteVisit(visit_id=VISIT_ID), now=NOW)


@pytest.mark.parametrize(
    "current_status",
    [VisitStatus.PLANNED, VisitStatus.ARRIVED],
)
@pytest.mark.unit
def test_complete_rejects_pre_work_statuses(current_status: VisitStatus) -> None:
    """Pre-work Visits cannot be completed -- they must use cancel_visit."""
    with pytest.raises(VisitCannotCompleteError):
        decide(
            state=make_visit(current_status),
            command=CompleteVisit(visit_id=VISIT_ID),
            now=NOW,
        )
