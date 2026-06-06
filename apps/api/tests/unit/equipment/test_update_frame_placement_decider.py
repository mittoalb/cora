"""Unit tests for the `update_frame_placement` slice's pure decider."""

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
    FrameCannotUpdateError,
    FrameNotFoundError,
    FramePlacementUpdated,
    FrameStatus,
    InvalidFrameRootError,
)
from cora.equipment.aggregates.frame.state import FrameName
from cora.equipment.features import update_frame_placement
from cora.equipment.features.update_frame_placement import UpdateFramePlacement

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)


def _placement(parent: object, *, z: float = 259313.0) -> Placement:
    return Placement(
        x=0.0,
        y=0.0,
        z=z,
        rx=0.0,
        ry=0.0,
        rz=0.0,
        parent_frame_id=parent,  # type: ignore[arg-type]
        reference_surface=ReferenceSurface.SHIELDING_FACE,
        tol_x=0.25,
        tol_y=0.25,
        tol_z=5.0,
        tol_rx=0.0,
        tol_ry=0.0,
        tol_rz=0.0,
        units=UnitSystem.SI_MM_RAD,
    )


def _frame(*, parent: object, status: FrameStatus = FrameStatus.ACTIVE) -> Frame:
    return Frame(
        id=uuid4(),
        name=FrameName("centerline_5p1_mrad"),
        parent_id=parent,  # type: ignore[arg-type]
        placement=_placement(parent),
        status=status,
    )


@pytest.mark.unit
def test_decide_emits_frame_placement_updated_when_new_placement_differs() -> None:
    parent = uuid4()
    frame = _frame(parent=parent)
    new_placement = _placement(parent, z=259999.0)
    events = update_frame_placement.decide(
        state=frame,
        command=UpdateFramePlacement(frame_id=frame.id, new_placement=new_placement, survey=None),
        now=_NOW,
    )
    assert events == [
        FramePlacementUpdated(
            frame_id=frame.id,
            new_placement=new_placement,
            survey=None,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_returns_no_op_when_new_placement_equals_current() -> None:
    """Idempotent contract (make_frame_update_handler precedent)."""
    parent = uuid4()
    frame = _frame(parent=parent)
    same_placement = _placement(parent)
    assert frame.placement == same_placement
    events = update_frame_placement.decide(
        state=frame,
        command=UpdateFramePlacement(frame_id=frame.id, new_placement=same_placement, survey=None),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_decide_raises_frame_not_found_when_state_is_none() -> None:
    frame_id = uuid4()
    parent = uuid4()
    with pytest.raises(FrameNotFoundError) as info:
        update_frame_placement.decide(
            state=None,
            command=UpdateFramePlacement(
                frame_id=frame_id,
                new_placement=_placement(parent),
                survey=None,
            ),
            now=_NOW,
        )
    assert info.value.frame_id == frame_id


@pytest.mark.unit
def test_decide_raises_frame_cannot_update_when_decommissioned() -> None:
    parent = uuid4()
    frame = _frame(parent=parent, status=FrameStatus.DECOMMISSIONED)
    with pytest.raises(FrameCannotUpdateError) as info:
        update_frame_placement.decide(
            state=frame,
            command=UpdateFramePlacement(
                frame_id=frame.id,
                new_placement=_placement(parent, z=259999.0),
                survey=None,
            ),
            now=_NOW,
        )
    assert info.value.frame_id == frame.id
    assert "Decommissioned" in info.value.reason


@pytest.mark.unit
def test_decide_raises_frame_cannot_update_when_state_is_root_frame() -> None:
    """Root frames have placement=None; updating them
    would create a placement on a root, violating the invariant."""
    root = Frame(
        id=uuid4(),
        name=FrameName("centerline_1p35_mrad"),
        parent_id=None,
        placement=None,
        status=FrameStatus.ACTIVE,
    )
    with pytest.raises(FrameCannotUpdateError) as info:
        update_frame_placement.decide(
            state=root,
            command=UpdateFramePlacement(
                frame_id=root.id,
                new_placement=_placement(uuid4()),
                survey=None,
            ),
            now=_NOW,
        )
    assert "root frame" in info.value.reason.lower()


@pytest.mark.unit
def test_decide_rejects_new_placement_whose_parent_does_not_match_frames_parent() -> None:
    """update_frame_placement cannot reparent: new_placement.parent_frame_id MUST
    equal the Frame's existing parent_id."""
    parent = uuid4()
    other = uuid4()
    frame = _frame(parent=parent)
    with pytest.raises(InvalidFrameRootError) as info:
        update_frame_placement.decide(
            state=frame,
            command=UpdateFramePlacement(
                frame_id=frame.id,
                new_placement=_placement(other, z=259999.0),
                survey=None,
            ),
            now=_NOW,
        )
    assert "reparent" in info.value.reason.lower() or "parent" in info.value.reason.lower()
