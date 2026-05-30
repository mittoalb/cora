"""Decider tests for `release_control_of_surface`."""

from uuid import uuid4

import pytest

from cora.trust.aggregates.visit import (
    VisitCannotReleaseControlError,
    VisitNotFoundError,
    VisitReleasedControlOfSurface,
    VisitStatus,
)
from cora.trust.features.release_control_of_surface import ReleaseControlOfSurface
from cora.trust.features.release_control_of_surface.context import (
    ReleaseControlOfSurfaceContext,
)
from cora.trust.features.release_control_of_surface.decider import decide
from cora.trust.projections.surface_active_visit import SurfaceActiveVisit
from tests.unit.trust.visit._fixtures import NOW, SURFACE_ID, VISIT_ID, make_visit

_CMD = ReleaseControlOfSurface(visit_id=VISIT_ID, surface_id=SURFACE_ID)


@pytest.mark.unit
def test_release_by_current_holder_emits_event() -> None:
    state = make_visit(VisitStatus.IN_PROGRESS)
    ctx = ReleaseControlOfSurfaceContext(
        active_holder=SurfaceActiveVisit(visit_id=state.id, since_at=NOW)
    )
    events = decide(state=state, command=_CMD, context=ctx, now=NOW)
    assert len(events) == 1
    [e] = events
    assert isinstance(e, VisitReleasedControlOfSurface)
    assert e.visit_id == state.id
    assert e.surface_id == SURFACE_ID
    assert e.occurred_at == NOW


@pytest.mark.unit
def test_release_raises_not_found_on_empty_state() -> None:
    ctx = ReleaseControlOfSurfaceContext(active_holder=None)
    with pytest.raises(VisitNotFoundError):
        decide(state=None, command=_CMD, context=ctx, now=NOW)


@pytest.mark.unit
def test_release_rejects_when_free_surface() -> None:
    state = make_visit(VisitStatus.IN_PROGRESS)
    ctx = ReleaseControlOfSurfaceContext(active_holder=None)
    with pytest.raises(VisitCannotReleaseControlError) as exc_info:
        decide(state=state, command=_CMD, context=ctx, now=NOW)
    assert exc_info.value.reason == "not_holder"
    assert exc_info.value.current_holder_id is None


@pytest.mark.unit
def test_release_rejects_when_other_visit_holds() -> None:
    state = make_visit(VisitStatus.IN_PROGRESS)
    other = uuid4()
    ctx = ReleaseControlOfSurfaceContext(
        active_holder=SurfaceActiveVisit(visit_id=other, since_at=NOW)
    )
    with pytest.raises(VisitCannotReleaseControlError) as exc_info:
        decide(state=state, command=_CMD, context=ctx, now=NOW)
    assert exc_info.value.reason == "not_holder"
    assert exc_info.value.current_holder_id == other


@pytest.mark.unit
def test_release_rejects_surface_mismatch_with_distinct_reason() -> None:
    state = make_visit(VisitStatus.IN_PROGRESS)
    other_surface = uuid4()
    ctx = ReleaseControlOfSurfaceContext(
        active_holder=SurfaceActiveVisit(visit_id=state.id, since_at=NOW)
    )
    with pytest.raises(VisitCannotReleaseControlError) as exc_info:
        decide(
            state=state,
            command=ReleaseControlOfSurface(visit_id=VISIT_ID, surface_id=other_surface),
            context=ctx,
            now=NOW,
        )
    assert exc_info.value.reason == "surface_mismatch"


@pytest.mark.unit
def test_release_error_str_does_not_leak_holder_id() -> None:
    state = make_visit(VisitStatus.IN_PROGRESS)
    other = uuid4()
    ctx = ReleaseControlOfSurfaceContext(
        active_holder=SurfaceActiveVisit(visit_id=other, since_at=NOW)
    )
    with pytest.raises(VisitCannotReleaseControlError) as exc_info:
        decide(state=state, command=_CMD, context=ctx, now=NOW)
    assert str(other) not in str(exc_info.value)
