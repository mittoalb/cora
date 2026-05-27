"""Decider tests for `void_visit` (any non-terminal -> Voided + reason).

FHIR R5 entered-in-error analog. Distinct from cancel_visit (real
allocation, pre-work) and abort_visit (real work stopped). Use cases:
BSS double-sent registration, duplicate Visit, registration error.
"""

import pytest

from cora.trust.aggregates.visit import (
    InvalidVisitReasonError,
    VisitNotFoundError,
    VisitStatus,
    VisitVoided,
)
from cora.trust.features.void_visit import VoidVisit
from cora.trust.features.void_visit.decider import decide
from tests.unit.trust.visit._fixtures import NOW, VISIT_ID, make_visit


@pytest.mark.parametrize(
    "from_status",
    [
        VisitStatus.PLANNED,
        VisitStatus.ARRIVED,
        VisitStatus.IN_PROGRESS,
        VisitStatus.ON_HOLD,
    ],
)
@pytest.mark.unit
def test_void_from_any_non_terminal_status_emits_visit_voided(from_status: VisitStatus) -> None:
    events = decide(
        state=make_visit(from_status),
        command=VoidVisit(visit_id=VISIT_ID, reason="BSS double-sent registration"),
        now=NOW,
    )
    [e] = events
    assert isinstance(e, VisitVoided)
    assert e.reason == "BSS double-sent registration"


@pytest.mark.unit
def test_void_trims_reason() -> None:
    events = decide(
        state=make_visit(VisitStatus.PLANNED),
        command=VoidVisit(visit_id=VISIT_ID, reason="  trimmed  "),
        now=NOW,
    )
    assert events[0].reason == "trimmed"


@pytest.mark.unit
def test_void_rejects_empty_reason() -> None:
    with pytest.raises(InvalidVisitReasonError):
        decide(
            state=make_visit(VisitStatus.PLANNED),
            command=VoidVisit(visit_id=VISIT_ID, reason="\t"),
            now=NOW,
        )


@pytest.mark.unit
def test_void_raises_not_found_on_empty_state() -> None:
    with pytest.raises(VisitNotFoundError):
        decide(state=None, command=VoidVisit(visit_id=VISIT_ID, reason="r"), now=NOW)
