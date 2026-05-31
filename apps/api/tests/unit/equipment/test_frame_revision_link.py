"""Unit tests for the FrameRevisionLink VO and InvalidFrameRevisionError.

Mirrors test_placement_value_object.py: tests focus on within-VO
invariants (transform.parent_frame_id must equal predecessor_frame_id),
construction with valid inputs, and frozen/structural equality.

Cross-Frame invariants (self-supersession, predecessor existence) are
decider/handler concerns and live in test_register_frame_decider.py.
"""

from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from cora.equipment.aggregates._placement import (
    Placement,
    ReferenceSurface,
    UnitSystem,
)
from cora.equipment.aggregates.frame import (
    FrameRevisionLink,
    InvalidFrameRevisionError,
)


def _transform_against(predecessor_id: object) -> Placement:
    """Build a Placement whose parent_frame is the given predecessor id."""
    return Placement(
        x=0.0,
        y=0.0,
        z=1822.0,
        rx=0.0,
        ry=0.0,
        rz=0.0,
        parent_frame_id=predecessor_id,  # type: ignore[arg-type]
        reference_surface=ReferenceSurface.OPTIC_CENTER,
        tol_x=0.0,
        tol_y=0.0,
        tol_z=5.0,
        tol_rx=0.0,
        tol_ry=0.0,
        tol_rz=0.0,
        units=UnitSystem.SI_MM_RAD,
    )


@pytest.mark.unit
def test_frame_revision_link_constructs_with_matching_transform_parent() -> None:
    predecessor = uuid4()
    link = FrameRevisionLink(
        predecessor_frame_id=predecessor,
        transform_from_predecessor=_transform_against(predecessor),
    )
    assert link.predecessor_frame_id == predecessor
    assert link.transform_from_predecessor.parent_frame_id == predecessor
    assert link.transform_from_predecessor.z == 1822.0


@pytest.mark.unit
def test_frame_revision_link_rejects_transform_pointing_at_different_parent() -> None:
    predecessor = uuid4()
    different = uuid4()
    with pytest.raises(InvalidFrameRevisionError) as exc_info:
        FrameRevisionLink(
            predecessor_frame_id=predecessor,
            transform_from_predecessor=_transform_against(different),
        )
    msg = str(exc_info.value)
    assert "transform.parent_frame_id" in msg
    assert "predecessor_frame_id" in msg
    assert str(predecessor) in msg
    assert str(different) in msg


@pytest.mark.unit
def test_frame_revision_link_is_frozen() -> None:
    predecessor = uuid4()
    link = FrameRevisionLink(
        predecessor_frame_id=predecessor,
        transform_from_predecessor=_transform_against(predecessor),
    )
    with pytest.raises(FrozenInstanceError):
        link.predecessor_frame_id = uuid4()  # type: ignore[misc]


@pytest.mark.unit
def test_frame_revision_link_equality_is_structural() -> None:
    predecessor = uuid4()
    transform = _transform_against(predecessor)
    a = FrameRevisionLink(predecessor_frame_id=predecessor, transform_from_predecessor=transform)
    b = FrameRevisionLink(predecessor_frame_id=predecessor, transform_from_predecessor=transform)
    assert a == b
    other_predecessor = uuid4()
    c = FrameRevisionLink(
        predecessor_frame_id=other_predecessor,
        transform_from_predecessor=_transform_against(other_predecessor),
    )
    assert a != c


@pytest.mark.unit
def test_invalid_frame_revision_error_carries_reason() -> None:
    exc = InvalidFrameRevisionError("transform.parent_frame_id mismatch")
    assert exc.reason == "transform.parent_frame_id mismatch"
    assert "Invalid FrameRevisionLink" in str(exc)
    assert "transform.parent_frame_id mismatch" in str(exc)
