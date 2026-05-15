"""Pure-decider tests for `record_review_step_clearance` slice."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceCannotRecordReviewStepError,
    ClearanceKind,
    ClearanceNotFoundError,
    ClearanceReviewStepRecorded,
    ClearanceStatus,
    ClearanceTitle,
    InvalidClearanceReviewerNotesError,
    InvalidClearanceReviewerRoleError,
    InvalidClearanceReviewStepIndexError,
    ReviewerStep,
    RunBinding,
)
from cora.safety.aggregates.clearance.state import (
    CLEARANCE_REVIEWER_NOTES_MAX_LENGTH,
)
from cora.safety.features import record_review_step_clearance
from cora.safety.features.record_review_step_clearance import RecordReviewStepClearance

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_DECIDED = datetime(2026, 5, 15, 11, 0, 0, tzinfo=UTC)


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
def test_decide_emits_review_step_recorded_at_index_zero() -> None:
    state = _clearance()
    actor = uuid4()
    events = record_review_step_clearance.decide(
        state=state,
        command=RecordReviewStepClearance(
            clearance_id=state.id,
            step_index=0,
            role="BeamlineScientist",
            actor_id=actor,
            decision="Approved",
            decided_at=_DECIDED,
            notes="LGTM",
        ),
        now=_NOW,
    )
    assert events == [
        ClearanceReviewStepRecorded(
            clearance_id=state.id,
            step_index=0,
            role="BeamlineScientist",
            actor_id=actor,
            decision="Approved",
            decided_at=_DECIDED,
            notes="LGTM",
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_appends_at_correct_index_when_chain_has_prior_steps() -> None:
    prior = ReviewerStep(
        step_index=0,
        role="BeamlineScientist",
        actor_id=uuid4(),
        decision="Approved",
        decided_at=_DECIDED,
    )
    state = _clearance(reviewers=(prior,))
    actor = uuid4()
    events = record_review_step_clearance.decide(
        state=state,
        command=RecordReviewStepClearance(
            clearance_id=state.id,
            step_index=1,
            role="ESH",
            actor_id=actor,
            decision="Approved",
            decided_at=_DECIDED,
        ),
        now=_NOW,
    )
    assert events[0].step_index == 1


@pytest.mark.unit
def test_decide_rejects_wrong_step_index() -> None:
    state = _clearance()
    with pytest.raises(InvalidClearanceReviewStepIndexError):
        record_review_step_clearance.decide(
            state=state,
            command=RecordReviewStepClearance(
                clearance_id=state.id,
                step_index=1,  # state has 0 reviewers; expected index 0
                role="x",
                actor_id=uuid4(),
                decision="Approved",
                decided_at=_DECIDED,
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_empty_role() -> None:
    state = _clearance()
    with pytest.raises(InvalidClearanceReviewerRoleError):
        record_review_step_clearance.decide(
            state=state,
            command=RecordReviewStepClearance(
                clearance_id=state.id,
                step_index=0,
                role="   ",
                actor_id=uuid4(),
                decision="Approved",
                decided_at=_DECIDED,
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_oversized_notes() -> None:
    state = _clearance()
    with pytest.raises(InvalidClearanceReviewerNotesError):
        record_review_step_clearance.decide(
            state=state,
            command=RecordReviewStepClearance(
                clearance_id=state.id,
                step_index=0,
                role="x",
                actor_id=uuid4(),
                decision="Approved",
                decided_at=_DECIDED,
                notes="z" * (CLEARANCE_REVIEWER_NOTES_MAX_LENGTH + 1),
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_normalizes_whitespace_only_notes_to_none() -> None:
    state = _clearance()
    events = record_review_step_clearance.decide(
        state=state,
        command=RecordReviewStepClearance(
            clearance_id=state.id,
            step_index=0,
            role="x",
            actor_id=uuid4(),
            decision="Approved",
            decided_at=_DECIDED,
            notes="   ",
        ),
        now=_NOW,
    )
    assert events[0].notes is None


@pytest.mark.unit
def test_decide_rejects_when_state_none() -> None:
    cid = uuid4()
    with pytest.raises(ClearanceNotFoundError):
        record_review_step_clearance.decide(
            state=None,
            command=RecordReviewStepClearance(
                clearance_id=cid,
                step_index=0,
                role="x",
                actor_id=uuid4(),
                decision="Approved",
                decided_at=_DECIDED,
            ),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_rejects_when_status_not_under_review() -> None:
    state = _clearance(status=ClearanceStatus.SUBMITTED)
    with pytest.raises(ClearanceCannotRecordReviewStepError):
        record_review_step_clearance.decide(
            state=state,
            command=RecordReviewStepClearance(
                clearance_id=state.id,
                step_index=0,
                role="x",
                actor_id=uuid4(),
                decision="Approved",
                decided_at=_DECIDED,
            ),
            now=_NOW,
        )
