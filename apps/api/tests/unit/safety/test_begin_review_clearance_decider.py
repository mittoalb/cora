"""Pure-decider tests for `begin_review_clearance` slice."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceCannotBeginReviewError,
    ClearanceKind,
    ClearanceNotFoundError,
    ClearanceStatus,
    ClearanceTitle,
    ClearanceUnderReview,
    InvalidClearanceReviewerRoleError,
    RunBinding,
)
from cora.safety.features import begin_review_clearance
from cora.safety.features.begin_review_clearance import BeginReviewClearance

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


def _clearance(status: ClearanceStatus = ClearanceStatus.SUBMITTED) -> Clearance:
    return Clearance(
        id=uuid4(),
        kind=ClearanceKind.ESAF,
        facility_asset_id=uuid4(),
        title=ClearanceTitle("Pilot"),
        bindings=frozenset({RunBinding(run_id=uuid4())}),
        status=status,
    )


@pytest.mark.unit
def test_decide_emits_under_review_from_submitted() -> None:
    state = _clearance(ClearanceStatus.SUBMITTED)
    events = begin_review_clearance.decide(
        state=state,
        command=BeginReviewClearance(
            clearance_id=state.id,
            first_reviewer_role="BeamlineScientist",
        ),
        now=_NOW,
    )
    assert events == [
        ClearanceUnderReview(
            clearance_id=state.id,
            first_reviewer_role="BeamlineScientist",
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_trims_role() -> None:
    state = _clearance(ClearanceStatus.SUBMITTED)
    events = begin_review_clearance.decide(
        state=state,
        command=BeginReviewClearance(clearance_id=state.id, first_reviewer_role="  ESH  "),
        now=_NOW,
    )
    assert events[0].first_reviewer_role == "ESH"


@pytest.mark.unit
def test_decide_rejects_empty_role() -> None:
    state = _clearance(ClearanceStatus.SUBMITTED)
    with pytest.raises(InvalidClearanceReviewerRoleError):
        begin_review_clearance.decide(
            state=state,
            command=BeginReviewClearance(clearance_id=state.id, first_reviewer_role="   "),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_when_state_none() -> None:
    cid = uuid4()
    with pytest.raises(ClearanceNotFoundError):
        begin_review_clearance.decide(
            state=None,
            command=BeginReviewClearance(clearance_id=cid, first_reviewer_role="x"),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_when_status_not_submitted() -> None:
    state = _clearance(ClearanceStatus.DEFINED)
    with pytest.raises(ClearanceCannotBeginReviewError):
        begin_review_clearance.decide(
            state=state,
            command=BeginReviewClearance(clearance_id=state.id, first_reviewer_role="x"),
            now=_NOW,
        )
