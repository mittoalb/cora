"""Decider tests for `cancel_visit` (Planned | Arrived -> Cancelled + reason).

HL7 v2 A11 precedent (cancel-admit, pre-work). Distinct from
abort_visit (mid-work) and void_visit (registration error).
"""

import pytest

from cora.trust.aggregates.visit import (
    InvalidVisitReasonError,
    VisitCancelled,
    VisitCannotCancelError,
    VisitNotFoundError,
    VisitStatus,
)
from cora.trust.features.cancel_visit import CancelVisit
from cora.trust.features.cancel_visit.decider import decide
from tests.unit.trust.visit._fixtures import NOW, VISIT_ID, make_visit


@pytest.mark.parametrize(
    "from_status",
    [VisitStatus.PLANNED, VisitStatus.ARRIVED],
)
@pytest.mark.unit
def test_cancel_from_pre_work_statuses_emits_visit_cancelled(from_status: VisitStatus) -> None:
    events = decide(
        state=make_visit(from_status),
        command=CancelVisit(visit_id=VISIT_ID, reason="no-show"),
        now=NOW,
    )
    [e] = events
    assert isinstance(e, VisitCancelled)
    assert e.reason == "no-show"


@pytest.mark.unit
def test_cancel_trims_reason() -> None:
    events = decide(
        state=make_visit(VisitStatus.PLANNED),
        command=CancelVisit(visit_id=VISIT_ID, reason="  trimmed  "),
        now=NOW,
    )
    assert events[0].reason == "trimmed"


@pytest.mark.unit
def test_cancel_rejects_empty_reason() -> None:
    with pytest.raises(InvalidVisitReasonError):
        decide(
            state=make_visit(VisitStatus.PLANNED),
            command=CancelVisit(visit_id=VISIT_ID, reason="  "),
            now=NOW,
        )


@pytest.mark.unit
def test_cancel_raises_not_found_on_empty_state() -> None:
    with pytest.raises(VisitNotFoundError):
        decide(state=None, command=CancelVisit(visit_id=VISIT_ID, reason="r"), now=NOW)


@pytest.mark.parametrize(
    "current_status",
    [VisitStatus.IN_PROGRESS, VisitStatus.ON_HOLD],
)
@pytest.mark.unit
def test_cancel_rejects_post_work_statuses_must_use_abort(current_status: VisitStatus) -> None:
    """HL7 v2 A11 vs A13 distinction: cancel is pre-work only. Mid-work
    Visits must use abort_visit instead."""
    with pytest.raises(VisitCannotCancelError):
        decide(
            state=make_visit(current_status),
            command=CancelVisit(visit_id=VISIT_ID, reason="r"),
            now=NOW,
        )
