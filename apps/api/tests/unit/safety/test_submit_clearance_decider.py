"""Pure-decider tests for `submit_clearance` slice."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceCannotSubmitError,
    ClearanceKind,
    ClearanceNotFoundError,
    ClearanceStatus,
    ClearanceSubmitted,
    ClearanceTitle,
    RunBinding,
)
from cora.safety.features import submit_clearance
from cora.safety.features.submit_clearance import SubmitClearance

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


def _clearance(status: ClearanceStatus = ClearanceStatus.DEFINED) -> Clearance:
    return Clearance(
        id=uuid4(),
        kind=ClearanceKind.ESAF,
        facility_asset_id=uuid4(),
        title=ClearanceTitle("Pilot"),
        bindings=frozenset({RunBinding(run_id=uuid4())}),
        status=status,
    )


@pytest.mark.unit
def test_decide_emits_clearance_submitted_from_defined() -> None:
    state = _clearance(ClearanceStatus.DEFINED)
    events = submit_clearance.decide(
        state=state,
        command=SubmitClearance(clearance_id=state.id),
        now=_NOW,
    )
    assert events == [ClearanceSubmitted(clearance_id=state.id, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_rejects_when_state_none() -> None:
    cid = uuid4()
    with pytest.raises(ClearanceNotFoundError):
        submit_clearance.decide(
            state=None,
            command=SubmitClearance(clearance_id=cid),
            now=_NOW,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "current_status",
    [
        ClearanceStatus.SUBMITTED,
        ClearanceStatus.UNDER_REVIEW,
        ClearanceStatus.APPROVED,
        ClearanceStatus.ACTIVE,
        ClearanceStatus.EXPIRED,
        ClearanceStatus.REJECTED,
        ClearanceStatus.SUPERSEDED,
    ],
)
def test_decide_rejects_when_status_not_defined(current_status: ClearanceStatus) -> None:
    state = _clearance(current_status)
    with pytest.raises(ClearanceCannotSubmitError):
        submit_clearance.decide(
            state=state,
            command=SubmitClearance(clearance_id=state.id),
            now=_NOW,
        )
