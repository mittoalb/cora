"""Unit tests for the `decommission_frame` slice's pure decider."""

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
    FrameCannotDecommissionError,
    FrameDecommissioned,
    FrameInUseError,
    FrameNotFoundError,
    FrameStatus,
)
from cora.equipment.aggregates.frame.state import FrameName
from cora.equipment.features import decommission_frame
from cora.equipment.features.decommission_frame import (
    DecommissionFrame,
    DecommissionFrameContext,
)

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


def _frame(status: FrameStatus = FrameStatus.ACTIVE) -> Frame:
    parent = uuid4()
    return Frame(
        id=uuid4(),
        name=FrameName("centerline_5p1_mrad"),
        parent_frame_id=parent,
        placement_relative_to_parent=_placement(parent),
        status=status,
    )


@pytest.mark.unit
def test_decide_emits_frame_decommissioned_when_active_with_no_consumers() -> None:
    frame = _frame()
    events = decommission_frame.decide(
        state=frame,
        command=DecommissionFrame(frame_id=frame.id, reason="superseded by recal"),
        context=DecommissionFrameContext(active_consumer_ids=()),
        now=_NOW,
    )
    assert events == [
        FrameDecommissioned(
            frame_id=frame.id,
            reason="superseded by recal",
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_raises_frame_not_found_when_state_is_none() -> None:
    frame_id = uuid4()
    with pytest.raises(FrameNotFoundError) as info:
        decommission_frame.decide(
            state=None,
            command=DecommissionFrame(frame_id=frame_id, reason="x"),
            context=DecommissionFrameContext(active_consumer_ids=()),
            now=_NOW,
        )
    assert info.value.frame_id == frame_id


@pytest.mark.unit
def test_decide_raises_frame_cannot_decommission_when_already_decommissioned() -> None:
    frame = _frame(status=FrameStatus.DECOMMISSIONED)
    with pytest.raises(FrameCannotDecommissionError) as info:
        decommission_frame.decide(
            state=frame,
            command=DecommissionFrame(frame_id=frame.id, reason="x"),
            context=DecommissionFrameContext(active_consumer_ids=()),
            now=_NOW,
        )
    assert info.value.frame_id == frame.id
    assert "Decommissioned" in info.value.reason


@pytest.mark.unit
def test_decide_raises_frame_in_use_when_context_lists_active_consumers() -> None:
    frame = _frame()
    consumer_a = uuid4()
    consumer_b = uuid4()
    with pytest.raises(FrameInUseError) as info:
        decommission_frame.decide(
            state=frame,
            command=DecommissionFrame(frame_id=frame.id, reason="x"),
            context=DecommissionFrameContext(active_consumer_ids=(consumer_a, consumer_b)),
            now=_NOW,
        )
    assert info.value.frame_id == frame.id
    assert info.value.consumer_ids == (consumer_a, consumer_b)


@pytest.mark.unit
def test_decide_emits_when_consumers_tuple_is_empty() -> None:
    """Sanity: an empty tuple is the green-light precondition."""
    frame = _frame()
    events = decommission_frame.decide(
        state=frame,
        command=DecommissionFrame(frame_id=frame.id, reason="x"),
        context=DecommissionFrameContext(active_consumer_ids=()),
        now=_NOW,
    )
    assert len(events) == 1
    assert isinstance(events[0], FrameDecommissioned)
