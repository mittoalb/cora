"""Pure-decider tests for `activate_clearance` slice."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceActivated,
    ClearanceCannotActivateError,
    ClearanceKind,
    ClearanceNotFoundError,
    ClearanceStatus,
    ClearanceTitle,
    RunBinding,
)
from cora.safety.features import activate_clearance
from cora.safety.features.activate_clearance import ActivateClearance
from cora.shared.facility_code import FacilityCode

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


def _clearance(status: ClearanceStatus = ClearanceStatus.APPROVED) -> Clearance:
    return Clearance(
        id=uuid4(),
        kind=ClearanceKind.ESAF,
        facility_code=FacilityCode("aps"),
        title=ClearanceTitle("Pilot"),
        bindings=frozenset({RunBinding(run_id=uuid4())}),
        status=status,
    )


@pytest.mark.unit
def test_decide_emits_activated_from_approved() -> None:
    state = _clearance(ClearanceStatus.APPROVED)
    events = activate_clearance.decide(
        state=state,
        command=ActivateClearance(clearance_id=state.id),
        now=_NOW,
    )
    assert events == [ClearanceActivated(clearance_id=state.id, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_rejects_when_state_none() -> None:
    cid = uuid4()
    with pytest.raises(ClearanceNotFoundError):
        activate_clearance.decide(
            state=None,
            command=ActivateClearance(clearance_id=cid),
            now=_NOW,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "current_status",
    [
        ClearanceStatus.DEFINED,
        ClearanceStatus.SUBMITTED,
        ClearanceStatus.UNDER_REVIEW,
        ClearanceStatus.ACTIVE,
        ClearanceStatus.EXPIRED,
        ClearanceStatus.REJECTED,
        ClearanceStatus.SUPERSEDED,
    ],
)
def test_decide_rejects_when_status_not_approved(current_status: ClearanceStatus) -> None:
    state = _clearance(current_status)
    with pytest.raises(ClearanceCannotActivateError):
        activate_clearance.decide(
            state=state,
            command=ActivateClearance(clearance_id=state.id),
            now=_NOW,
        )
