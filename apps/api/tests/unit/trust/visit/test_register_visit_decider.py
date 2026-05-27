"""Decider tests for the `register_visit` slice (genesis)."""

from dataclasses import replace
from datetime import timedelta

import pytest

from cora.infrastructure.external_ref import ExternalRef
from cora.trust.aggregates.visit import (
    InvalidVisitPlannedPeriodError,
    Visit,
    VisitAlreadyExistsError,
    VisitRegistered,
    VisitStatus,
    VisitType,
)
from cora.trust.features.register_visit import RegisterVisit
from cora.trust.features.register_visit.decider import decide
from tests.unit.trust.visit._fixtures import (
    NOW,
    PLANNED_END,
    PLANNED_START,
    POLICY_ID,
    SURFACE_ID,
    VISIT_ID,
    make_visit,
)

_BASE_CMD = RegisterVisit(
    visit_id=VISIT_ID,
    policy_id=POLICY_ID,
    surface_id=SURFACE_ID,
    type=VisitType.USER,
    planned_start_at=PLANNED_START,
    planned_end_at=PLANNED_END,
)


@pytest.mark.unit
def test_genesis_emits_visit_registered() -> None:
    events = decide(state=None, command=_BASE_CMD, now=NOW)
    assert len(events) == 1
    [e] = events
    assert isinstance(e, VisitRegistered)
    assert e.visit_id == VISIT_ID
    assert e.policy_id == POLICY_ID
    assert e.surface_id == SURFACE_ID
    assert e.type == VisitType.USER.value
    assert e.planned_start_at == PLANNED_START
    assert e.planned_end_at == PLANNED_END
    assert e.occurred_at == NOW
    assert e.part_of_visit_id is None
    assert e.external_refs == frozenset()


@pytest.mark.unit
def test_genesis_carries_external_refs_through_to_event() -> None:
    ref = ExternalRef(scheme="proposal", id="12345")
    events = decide(state=None, command=replace(_BASE_CMD, external_refs=frozenset({ref})), now=NOW)
    assert events[0].external_refs == frozenset({ref})


@pytest.mark.unit
def test_genesis_carries_part_of_visit_id() -> None:
    from uuid import uuid4

    parent = uuid4()
    events = decide(state=None, command=replace(_BASE_CMD, part_of_visit_id=parent), now=NOW)
    assert events[0].part_of_visit_id == parent


@pytest.mark.unit
def test_genesis_rejects_existing_state() -> None:
    existing: Visit = make_visit(VisitStatus.PLANNED)
    with pytest.raises(VisitAlreadyExistsError) as exc_info:
        decide(state=existing, command=_BASE_CMD, now=NOW)
    assert exc_info.value.visit_id == existing.id


@pytest.mark.unit
def test_genesis_rejects_planned_end_equal_to_start() -> None:
    with pytest.raises(InvalidVisitPlannedPeriodError):
        decide(state=None, command=replace(_BASE_CMD, planned_end_at=PLANNED_START), now=NOW)


@pytest.mark.unit
def test_genesis_rejects_planned_end_before_start() -> None:
    with pytest.raises(InvalidVisitPlannedPeriodError):
        decide(
            state=None,
            command=replace(_BASE_CMD, planned_end_at=PLANNED_START - timedelta(hours=1)),
            now=NOW,
        )


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    cmd = replace(_BASE_CMD)  # explicit copy to validate purity, not aliasing
    first = decide(state=None, command=cmd, now=NOW)
    second = decide(state=None, command=cmd, now=NOW)
    assert first == second
