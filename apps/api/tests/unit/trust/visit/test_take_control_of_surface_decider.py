"""Decider tests for `take_control_of_surface`."""

from dataclasses import replace
from uuid import uuid4

import pytest

from cora.trust.aggregates.visit import (
    VisitCannotTakeControlError,
    VisitNotFoundError,
    VisitStatus,
    VisitSurfaceControlTaken,
)
from cora.trust.features.take_control_of_surface import TakeControlOfSurface
from cora.trust.features.take_control_of_surface.context import TakeControlOfSurfaceContext
from cora.trust.features.take_control_of_surface.decider import decide
from cora.trust.projections.surface_active_visit import SurfaceActiveVisit
from tests.unit.trust.visit._fixtures import NOW, SURFACE_ID, VISIT_ID, make_visit

_NO_HOLDER = TakeControlOfSurfaceContext(active_holder=None)
_CMD = TakeControlOfSurface(visit_id=VISIT_ID, surface_id=SURFACE_ID)


@pytest.mark.unit
def test_take_from_free_surface_in_progress_emits_event() -> None:
    events = decide(
        state=make_visit(VisitStatus.IN_PROGRESS),
        command=_CMD,
        context=_NO_HOLDER,
        now=NOW,
    )
    assert len(events) == 1
    [e] = events
    assert isinstance(e, VisitSurfaceControlTaken)
    assert e.visit_id == VISIT_ID
    assert e.surface_id == SURFACE_ID
    assert e.occurred_at == NOW


@pytest.mark.parametrize(
    "status",
    [VisitStatus.ARRIVED, VisitStatus.IN_PROGRESS, VisitStatus.ON_HOLD],
)
@pytest.mark.unit
def test_take_permitted_from_arrived_inprogress_onhold(status: VisitStatus) -> None:
    events = decide(
        state=make_visit(status),
        command=_CMD,
        context=_NO_HOLDER,
        now=NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_take_raises_not_found_on_empty_state() -> None:
    with pytest.raises(VisitNotFoundError):
        decide(state=None, command=_CMD, context=_NO_HOLDER, now=NOW)


@pytest.mark.unit
def test_take_rejects_planned_status() -> None:
    with pytest.raises(VisitCannotTakeControlError) as exc_info:
        decide(
            state=make_visit(VisitStatus.PLANNED),
            command=_CMD,
            context=_NO_HOLDER,
            now=NOW,
        )
    assert exc_info.value.reason == "status_not_eligible"


@pytest.mark.unit
def test_take_rejects_surface_mismatch() -> None:
    other_surface = uuid4()
    with pytest.raises(VisitCannotTakeControlError) as exc_info:
        decide(
            state=make_visit(VisitStatus.IN_PROGRESS),
            command=TakeControlOfSurface(visit_id=VISIT_ID, surface_id=other_surface),
            context=_NO_HOLDER,
            now=NOW,
        )
    assert exc_info.value.reason == "surface_mismatch"


@pytest.mark.unit
def test_take_rejects_when_surface_held_by_non_parent() -> None:
    other_visit = uuid4()
    ctx = TakeControlOfSurfaceContext(
        active_holder=SurfaceActiveVisit(visit_id=other_visit, since_at=NOW)
    )
    with pytest.raises(VisitCannotTakeControlError) as exc_info:
        decide(
            state=make_visit(VisitStatus.IN_PROGRESS),
            command=_CMD,
            context=ctx,
            now=NOW,
        )
    assert exc_info.value.reason == "not_descendant"


@pytest.mark.unit
def test_take_allowed_when_active_holder_is_parent() -> None:
    parent_id = uuid4()
    state = replace(make_visit(VisitStatus.IN_PROGRESS), part_of_visit_id=parent_id)
    ctx = TakeControlOfSurfaceContext(
        active_holder=SurfaceActiveVisit(visit_id=parent_id, since_at=NOW)
    )
    events = decide(state=state, command=_CMD, context=ctx, now=NOW)
    assert len(events) == 1


@pytest.mark.unit
def test_take_self_holding_is_idempotent_emits_event() -> None:
    state = make_visit(VisitStatus.IN_PROGRESS)
    ctx = TakeControlOfSurfaceContext(
        active_holder=SurfaceActiveVisit(visit_id=state.id, since_at=NOW)
    )
    events = decide(state=state, command=_CMD, context=ctx, now=NOW)
    assert len(events) == 1
