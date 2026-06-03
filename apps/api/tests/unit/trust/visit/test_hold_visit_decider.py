"""Decider tests for `hold_visit` (InProgress -> OnHold + reason)."""

import pytest

from cora.trust.aggregates.visit import (
    InvalidVisitReasonError,
    VisitCannotHoldError,
    VisitHeld,
    VisitNotFoundError,
    VisitStatus,
)
from cora.trust.features.hold_visit import HoldVisit
from cora.trust.features.hold_visit.decider import decide
from tests.unit.trust.visit._fixtures import NOW, VISIT_ID, make_visit


@pytest.mark.unit
def test_hold_from_in_progress_emits_visit_held() -> None:
    events = decide(
        state=make_visit(VisitStatus.IN_PROGRESS),
        command=HoldVisit(visit_id=VISIT_ID, reason="beam dump"),
        now=NOW,
    )
    [e] = events
    assert isinstance(e, VisitHeld)
    assert e.reason == "beam dump"


@pytest.mark.unit
def test_hold_trims_reason() -> None:
    events = decide(
        state=make_visit(VisitStatus.IN_PROGRESS),
        command=HoldVisit(visit_id=VISIT_ID, reason="  trimmed  "),
        now=NOW,
    )
    assert events[0].reason == "trimmed"


@pytest.mark.parametrize("bad_reason", ["", "   ", "\n\t"])
@pytest.mark.unit
def test_hold_rejects_whitespace_reason(bad_reason: str) -> None:
    with pytest.raises(InvalidVisitReasonError):
        decide(
            state=make_visit(VisitStatus.IN_PROGRESS),
            command=HoldVisit(visit_id=VISIT_ID, reason=bad_reason),
            now=NOW,
        )


@pytest.mark.unit
def test_hold_rejects_too_long_reason() -> None:
    with pytest.raises(InvalidVisitReasonError):
        decide(
            state=make_visit(VisitStatus.IN_PROGRESS),
            command=HoldVisit(visit_id=VISIT_ID, reason="a" * 501),
            now=NOW,
        )


@pytest.mark.unit
def test_hold_raises_not_found_on_empty_state() -> None:
    with pytest.raises(VisitNotFoundError):
        decide(state=None, command=HoldVisit(visit_id=VISIT_ID, reason="r"), now=NOW)


@pytest.mark.parametrize(
    "current_status",
    [
        VisitStatus.PLANNED,
        VisitStatus.ARRIVED,
        VisitStatus.ON_HOLD,
    ],
)
@pytest.mark.unit
def test_hold_rejects_non_in_progress_statuses(current_status: VisitStatus) -> None:
    with pytest.raises(VisitCannotHoldError):
        decide(
            state=make_visit(current_status),
            command=HoldVisit(visit_id=VISIT_ID, reason="r"),
            now=NOW,
        )
