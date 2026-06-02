"""Decider tests for `abort_visit` (InProgress | OnHold -> Aborted + reason).

HL7 v2 A13 precedent (cancel-discharge, mid-work). Distinct from
cancel_visit (pre-work) and void_visit (registration error).
"""

import pytest

from cora.trust.aggregates.visit import (
    InvalidVisitReasonError,
    VisitAborted,
    VisitCannotAbortError,
    VisitNotFoundError,
    VisitStatus,
)
from cora.trust.features.abort_visit import AbortVisit
from cora.trust.features.abort_visit.decider import decide
from tests.unit.trust.visit._fixtures import NOW, VISIT_ID, make_visit


@pytest.mark.parametrize(
    "from_status",
    [VisitStatus.IN_PROGRESS, VisitStatus.ON_HOLD],
)
@pytest.mark.unit
def test_abort_from_post_work_statuses_emits_visit_aborted(from_status: VisitStatus) -> None:
    events = decide(
        state=make_visit(from_status),
        command=AbortVisit(visit_id=VISIT_ID, reason="equipment fault"),
        now=NOW,
    )
    [e] = events
    assert isinstance(e, VisitAborted)
    assert e.reason == "equipment fault"


@pytest.mark.unit
def test_abort_trims_reason() -> None:
    events = decide(
        state=make_visit(VisitStatus.IN_PROGRESS),
        command=AbortVisit(visit_id=VISIT_ID, reason="  trimmed  "),
        now=NOW,
    )
    assert events[0].reason == "trimmed"


@pytest.mark.unit
def test_abort_rejects_empty_reason() -> None:
    with pytest.raises(InvalidVisitReasonError):
        decide(
            state=make_visit(VisitStatus.IN_PROGRESS),
            command=AbortVisit(visit_id=VISIT_ID, reason=""),
            now=NOW,
        )


@pytest.mark.unit
def test_abort_raises_not_found_on_empty_state() -> None:
    with pytest.raises(VisitNotFoundError):
        decide(state=None, command=AbortVisit(visit_id=VISIT_ID, reason="r"), now=NOW)


@pytest.mark.parametrize(
    "current_status",
    [VisitStatus.PLANNED, VisitStatus.ARRIVED],
)
@pytest.mark.unit
def test_abort_rejects_pre_work_statuses_must_use_cancel(current_status: VisitStatus) -> None:
    """HL7 v2 A11 vs A13 distinction: abort is mid-work only. Pre-work
    Visits must use cancel_visit instead."""
    with pytest.raises(VisitCannotAbortError):
        decide(
            state=make_visit(current_status),
            command=AbortVisit(visit_id=VISIT_ID, reason="r"),
            now=NOW,
        )
