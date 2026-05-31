"""Unit tests for the `register_frame` slice's pure decider."""

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
    FrameAlreadyExistsError,
    FrameCannotSupersedeError,
    FrameRegistered,
    FrameRevisionLink,
    FrameStatus,
    InvalidFrameRootError,
)
from cora.equipment.aggregates.frame.state import FrameName, InvalidFrameNameError
from cora.equipment.features import register_frame
from cora.equipment.features.register_frame import RegisterFrame

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)


def _placement(parent: object) -> Placement:
    return Placement(
        x=0.0,
        y=0.0,
        z=259313.0,
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


@pytest.mark.unit
def test_decide_emits_frame_registered_for_root_frame() -> None:
    new_id = uuid4()
    events = register_frame.decide(
        state=None,
        command=RegisterFrame(
            name="centerline_1p35_mrad",
            parent_frame_id=None,
            placement=None,
        ),
        now=_NOW,
        new_id=new_id,
    )
    assert events == [
        FrameRegistered(
            frame_id=new_id,
            name="centerline_1p35_mrad",
            parent_frame_id=None,
            placement=None,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_emits_frame_registered_for_child_frame() -> None:
    new_id = uuid4()
    parent = uuid4()
    placement = _placement(parent)
    events = register_frame.decide(
        state=None,
        command=RegisterFrame(
            name="centerline_5p1_mrad",
            parent_frame_id=parent,
            placement=placement,
        ),
        now=_NOW,
        new_id=new_id,
    )
    assert len(events) == 1
    assert events[0].frame_id == new_id
    assert events[0].parent_frame_id == parent
    assert events[0].placement == placement


@pytest.mark.unit
def test_decide_rejects_root_frame_with_a_placement() -> None:
    """Root frame must have placement=None."""
    new_id = uuid4()
    with pytest.raises(InvalidFrameRootError) as info:
        register_frame.decide(
            state=None,
            command=RegisterFrame(
                name="centerline",
                parent_frame_id=None,
                placement=_placement(uuid4()),
            ),
            now=_NOW,
            new_id=new_id,
        )
    assert "Root frame" in info.value.reason


@pytest.mark.unit
def test_decide_rejects_child_frame_with_no_placement() -> None:
    """Child frame must have placement=non-None."""
    new_id = uuid4()
    parent = uuid4()
    with pytest.raises(InvalidFrameRootError) as info:
        register_frame.decide(
            state=None,
            command=RegisterFrame(
                name="centerline_5p1_mrad",
                parent_frame_id=parent,
                placement=None,
            ),
            now=_NOW,
            new_id=new_id,
        )
    assert "Child frame" in info.value.reason


@pytest.mark.unit
def test_decide_rejects_child_frame_when_placement_parent_mismatches_parent_frame_id() -> None:
    """The embedded Placement.parent_frame_id MUST equal the Frame's
    declared parent_frame_id (placement points where the Frame says)."""
    new_id = uuid4()
    parent = uuid4()
    other_parent = uuid4()
    bad_placement = _placement(other_parent)
    with pytest.raises(InvalidFrameRootError) as info:
        register_frame.decide(
            state=None,
            command=RegisterFrame(
                name="centerline_5p1_mrad",
                parent_frame_id=parent,
                placement=bad_placement,
            ),
            now=_NOW,
            new_id=new_id,
        )
    assert "Placement.parent_frame_id" in info.value.reason


@pytest.mark.unit
def test_decide_rejects_already_registered_frame() -> None:
    """State must be None (genesis-only)."""
    existing = Frame(
        id=uuid4(),
        name=FrameName("existing"),
        parent_frame_id=None,
        placement=None,
        status=FrameStatus.ACTIVE,
    )
    with pytest.raises(FrameAlreadyExistsError) as info:
        register_frame.decide(
            state=existing,
            command=RegisterFrame(
                name="new",
                parent_frame_id=None,
                placement=None,
            ),
            now=_NOW,
            new_id=uuid4(),
        )
    assert info.value.frame_id == existing.id


@pytest.mark.unit
def test_decide_rejects_whitespace_only_name() -> None:
    with pytest.raises(InvalidFrameNameError):
        register_frame.decide(
            state=None,
            command=RegisterFrame(
                name="   ",
                parent_frame_id=None,
                placement=None,
            ),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_emits_supersedes_link_into_frame_registered_event() -> None:
    """When the command carries a supersedes link, the emitted
    FrameRegistered event carries it through unchanged. Successor is
    registered as a root frame (sibling of predecessor); transform
    captures the coordinate shift."""
    new_id = uuid4()
    predecessor = uuid4()
    link = FrameRevisionLink(
        predecessor_frame_id=predecessor,
        transform_from_predecessor=_placement(predecessor),
    )
    events = register_frame.decide(
        state=None,
        command=RegisterFrame(
            name="centerline_apsu",
            parent_frame_id=None,
            placement=None,
            supersedes=link,
        ),
        now=_NOW,
        new_id=new_id,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, FrameRegistered)
    assert event.supersedes == link
    assert event.parent_frame_id is None
    assert event.placement is None


@pytest.mark.unit
def test_decide_defaults_supersedes_to_none_when_command_omits_it() -> None:
    """RegisterFrame.supersedes defaults to None; non-revision frames
    register exactly as before."""
    events = register_frame.decide(
        state=None,
        command=RegisterFrame(
            name="centerline_1p35_mrad",
            parent_frame_id=None,
            placement=None,
        ),
        now=_NOW,
        new_id=uuid4(),
    )
    assert isinstance(events[0], FrameRegistered)
    assert events[0].supersedes is None


@pytest.mark.unit
def test_decide_rejects_self_supersession() -> None:
    """A frame cannot supersede itself: predecessor_frame_id == new_id
    raises FrameCannotSupersedeError with the offending id in the
    reason."""
    new_id = uuid4()
    self_link = FrameRevisionLink(
        predecessor_frame_id=new_id,  # same as new_id => self-supersession
        transform_from_predecessor=_placement(new_id),
    )
    with pytest.raises(FrameCannotSupersedeError) as info:
        register_frame.decide(
            state=None,
            command=RegisterFrame(
                name="self_revising",
                parent_frame_id=None,
                placement=None,
                supersedes=self_link,
            ),
            now=_NOW,
            new_id=new_id,
        )
    assert info.value.frame_id == new_id
    assert "self-supersession" in info.value.reason
