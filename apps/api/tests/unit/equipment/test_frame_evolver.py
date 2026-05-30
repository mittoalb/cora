"""Unit tests for the Frame aggregate's evolver: genesis + transitions."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates._placement import (
    Placement,
    ReferenceSurface,
    UnitSystem,
)
from cora.equipment.aggregates.frame import (
    Frame,
    FrameDecommissioned,
    FrameRegistered,
    FrameStatus,
    FrameUpdated,
    evolve,
    fold,
)
from cora.equipment.aggregates.frame.state import FrameName

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)


def _placement(parent: object) -> Placement:
    return Placement(
        x=0.0,
        y=0.0,
        z=259313.0,
        rx=0.0,
        ry=0.0,
        rz=0.0,
        parent_frame=parent,  # type: ignore[arg-type]
        reference_surface=ReferenceSurface.SHIELDING_FACE,
        tol_x=0.25,
        tol_y=0.25,
        tol_z=5.0,
        tol_rx=0.0,
        tol_ry=0.0,
        tol_rz=0.0,
        units=UnitSystem.SI_MM_RAD,
    )


@pytest.mark.unit
def test_evolve_genesis_sets_active_status_for_root_frame() -> None:
    frame_id = uuid4()
    event = FrameRegistered(
        frame_id=frame_id,
        name="centerline_1p35_mrad",
        parent_frame_id=None,
        placement_relative_to_parent=None,
        occurred_at=_NOW,
    )
    state = evolve(None, event)
    assert state == Frame(
        id=frame_id,
        name=FrameName("centerline_1p35_mrad"),
        parent_frame_id=None,
        placement_relative_to_parent=None,
        status=FrameStatus.ACTIVE,
    )


@pytest.mark.unit
def test_evolve_genesis_sets_active_status_for_child_frame() -> None:
    frame_id = uuid4()
    parent = uuid4()
    placement = _placement(parent)
    event = FrameRegistered(
        frame_id=frame_id,
        name="centerline_5p1_mrad",
        parent_frame_id=parent,
        placement_relative_to_parent=placement,
        occurred_at=_NOW,
    )
    state = evolve(None, event)
    assert state.parent_frame_id == parent
    assert state.placement_relative_to_parent == placement
    assert state.status is FrameStatus.ACTIVE


@pytest.mark.unit
def test_evolve_frame_updated_changes_only_placement() -> None:
    frame_id = uuid4()
    parent = uuid4()
    prior = Frame(
        id=frame_id,
        name=FrameName("centerline_5p1_mrad"),
        parent_frame_id=parent,
        placement_relative_to_parent=_placement(parent),
        status=FrameStatus.ACTIVE,
    )
    new_placement = Placement(
        x=0.0,
        y=0.0,
        z=259320.0,
        rx=0.0,
        ry=0.0,
        rz=0.0,
        parent_frame=parent,
        reference_surface=ReferenceSurface.SHIELDING_FACE,
        tol_x=0.25,
        tol_y=0.25,
        tol_z=5.0,
        tol_rx=0.0,
        tol_ry=0.0,
        tol_rz=0.0,
        units=UnitSystem.SI_MM_RAD,
    )
    event = FrameUpdated(
        frame_id=frame_id,
        new_placement=new_placement,
        survey=None,
        occurred_at=_NOW,
    )
    state = evolve(prior, event)
    assert state.id == prior.id
    assert state.name == prior.name
    assert state.parent_frame_id == parent
    assert state.placement_relative_to_parent == new_placement
    assert state.status is FrameStatus.ACTIVE


@pytest.mark.unit
def test_evolve_frame_decommissioned_sets_terminal_status() -> None:
    frame_id = uuid4()
    parent = uuid4()
    placement = _placement(parent)
    prior = Frame(
        id=frame_id,
        name=FrameName("centerline_5p1_mrad"),
        parent_frame_id=parent,
        placement_relative_to_parent=placement,
        status=FrameStatus.ACTIVE,
    )
    event = FrameDecommissioned(
        frame_id=frame_id,
        reason="superseded by recalibration 2026-05-30",
        occurred_at=_NOW,
    )
    state = evolve(prior, event)
    assert state.status is FrameStatus.DECOMMISSIONED
    # placement + parent + name carry through
    assert state.placement_relative_to_parent == placement
    assert state.parent_frame_id == parent
    assert state.name == prior.name


@pytest.mark.unit
def test_evolve_transition_event_on_empty_state_raises() -> None:
    """Non-genesis events on empty state are stream corruption; raise loud."""
    parent = uuid4()
    event = FrameUpdated(
        frame_id=uuid4(),
        new_placement=_placement(parent),
        survey=None,
        occurred_at=_NOW,
    )
    with pytest.raises(ValueError, match="FrameUpdated"):
        evolve(None, event)


@pytest.mark.unit
def test_fold_replays_genesis_then_update_then_decommission() -> None:
    frame_id = uuid4()
    parent = uuid4()
    initial_placement = _placement(parent)
    updated_placement = Placement(
        x=1.0,
        y=2.0,
        z=3.0,
        rx=0.0,
        ry=0.0,
        rz=0.0,
        parent_frame=parent,
        reference_surface=ReferenceSurface.SHIELDING_FACE,
        tol_x=0.25,
        tol_y=0.25,
        tol_z=5.0,
        tol_rx=0.0,
        tol_ry=0.0,
        tol_rz=0.0,
        units=UnitSystem.SI_MM_RAD,
    )
    events = [
        FrameRegistered(
            frame_id=frame_id,
            name="centerline_5p1_mrad",
            parent_frame_id=parent,
            placement_relative_to_parent=initial_placement,
            occurred_at=_NOW,
        ),
        FrameUpdated(
            frame_id=frame_id,
            new_placement=updated_placement,
            survey={"instrument": "Leica AT960", "residual_mm": 0.18},
            occurred_at=_NOW,
        ),
        FrameDecommissioned(
            frame_id=frame_id,
            reason="superseded",
            occurred_at=_NOW,
        ),
    ]
    state = fold(events)
    assert state is not None
    assert state.id == frame_id
    assert state.placement_relative_to_parent == updated_placement
    assert state.status is FrameStatus.DECOMMISSIONED


@pytest.mark.unit
def test_fold_returns_none_for_empty_history() -> None:
    assert fold([]) is None
