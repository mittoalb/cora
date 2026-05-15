"""Pure-decider tests for `approve_clearance` slice."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceApproved,
    ClearanceCannotApproveError,
    ClearanceKind,
    ClearanceNotFoundError,
    ClearanceStatus,
    ClearanceTitle,
    InvalidClearanceValidityWindowError,
    ReviewerStep,
    RunBinding,
)
from cora.safety.features import approve_clearance
from cora.safety.features.approve_clearance import ApproveClearance

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


def _approving_step() -> ReviewerStep:
    return ReviewerStep(
        step_index=0,
        role="ESH",
        actor_id=uuid4(),
        decision="Approved",
        decided_at=_NOW,
    )


def _clearance(
    *,
    status: ClearanceStatus = ClearanceStatus.UNDER_REVIEW,
    reviewers: tuple[ReviewerStep, ...] = (),
) -> Clearance:
    return Clearance(
        id=uuid4(),
        kind=ClearanceKind.ESAF,
        facility_asset_id=uuid4(),
        title=ClearanceTitle("Pilot"),
        bindings=frozenset({RunBinding(run_id=uuid4())}),
        reviewers=reviewers,
        status=status,
    )


@pytest.mark.unit
def test_decide_emits_approved_when_chain_has_approving_step() -> None:
    state = _clearance(reviewers=(_approving_step(),))
    actor = uuid4()
    events = approve_clearance.decide(
        state=state,
        command=ApproveClearance(clearance_id=state.id, approving_actor_id=actor),
        now=_NOW,
    )
    assert events == [
        ClearanceApproved(
            clearance_id=state.id,
            approving_actor_id=actor,
            valid_from=None,
            valid_until=None,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_carries_validity_window_when_provided() -> None:
    state = _clearance(reviewers=(_approving_step(),))
    valid_from = datetime(2026, 5, 16, tzinfo=UTC)
    valid_until = datetime(2026, 6, 15, tzinfo=UTC)
    events = approve_clearance.decide(
        state=state,
        command=ApproveClearance(
            clearance_id=state.id,
            approving_actor_id=uuid4(),
            valid_from=valid_from,
            valid_until=valid_until,
        ),
        now=_NOW,
    )
    assert events[0].valid_from == valid_from
    assert events[0].valid_until == valid_until


@pytest.mark.unit
def test_decide_rejects_when_chain_has_no_approving_step() -> None:
    rejected_step = ReviewerStep(
        step_index=0,
        role="ESH",
        actor_id=uuid4(),
        decision="RequestedChanges",
        decided_at=_NOW,
    )
    state = _clearance(reviewers=(rejected_step,))
    with pytest.raises(ClearanceCannotApproveError, match="no approving"):
        approve_clearance.decide(
            state=state,
            command=ApproveClearance(clearance_id=state.id, approving_actor_id=uuid4()),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_when_chain_empty() -> None:
    state = _clearance(reviewers=())
    with pytest.raises(ClearanceCannotApproveError, match="no approving"):
        approve_clearance.decide(
            state=state,
            command=ApproveClearance(clearance_id=state.id, approving_actor_id=uuid4()),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_inverted_validity_window() -> None:
    state = _clearance(reviewers=(_approving_step(),))
    with pytest.raises(InvalidClearanceValidityWindowError):
        approve_clearance.decide(
            state=state,
            command=ApproveClearance(
                clearance_id=state.id,
                approving_actor_id=uuid4(),
                valid_from=datetime(2026, 6, 15, tzinfo=UTC),
                valid_until=datetime(2026, 5, 15, tzinfo=UTC),
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_when_state_none() -> None:
    cid = uuid4()
    with pytest.raises(ClearanceNotFoundError):
        approve_clearance.decide(
            state=None,
            command=ApproveClearance(clearance_id=cid, approving_actor_id=uuid4()),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_when_status_not_under_review() -> None:
    state = _clearance(status=ClearanceStatus.SUBMITTED, reviewers=(_approving_step(),))
    with pytest.raises(ClearanceCannotApproveError):
        approve_clearance.decide(
            state=state,
            command=ApproveClearance(clearance_id=state.id, approving_actor_id=uuid4()),
            now=_NOW,
        )
