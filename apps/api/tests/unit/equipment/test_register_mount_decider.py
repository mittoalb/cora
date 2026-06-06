"""Unit tests for the `register_mount` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates._drawing import Drawing, DrawingSystem
from cora.equipment.aggregates._placement import (
    Placement,
    ReferenceSurface,
    UnitSystem,
)
from cora.equipment.aggregates.mount import (
    InvalidSlotCodeError,
    Mount,
    MountAlreadyExistsError,
    MountRegistered,
    MountStatus,
)
from cora.equipment.aggregates.mount.state import SlotCode
from cora.equipment.features import register_mount
from cora.equipment.features.register_mount import RegisterMount, RegisterMountContext

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)


def _placement(parent_frame_id: object) -> Placement:
    return Placement(
        x=0.0,
        y=0.0,
        z=259313.0,
        rx=0.0,
        ry=0.0,
        rz=0.0,
        parent_frame_id=parent_frame_id,  # type: ignore[arg-type]
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
def test_decide_emits_mount_registered_for_top_level_slot() -> None:
    new_id = uuid4()
    frame_id = uuid4()
    events = register_mount.decide(
        state=None,
        command=RegisterMount(
            slot_code="02-BM-A-K-01",
            parent_id=None,
            placement=_placement(frame_id),
            drawing=None,
        ),
        context=RegisterMountContext(existing_mount_id=None),
        now=_NOW,
        new_id=new_id,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, MountRegistered)
    assert event.mount_id == new_id
    assert event.slot_code == "02-BM-A-K-01"
    assert event.parent_id is None
    assert event.drawing is None


@pytest.mark.unit
def test_decide_emits_mount_registered_for_child_slot_with_drawing() -> None:
    new_id = uuid4()
    parent_mount = uuid4()
    frame_id = uuid4()
    drawing = Drawing(system=DrawingSystem.ICMS, number="P4105", revision="A")
    events = register_mount.decide(
        state=None,
        command=RegisterMount(
            slot_code="child-01",
            parent_id=parent_mount,
            placement=_placement(frame_id),
            drawing=drawing,
        ),
        context=RegisterMountContext(existing_mount_id=None),
        now=_NOW,
        new_id=new_id,
    )
    assert events[0].parent_id == parent_mount
    assert events[0].drawing == drawing


@pytest.mark.unit
def test_decide_rejects_already_registered_stream() -> None:
    """State must be None (genesis-only)."""
    existing = Mount(
        id=uuid4(),
        slot_code=SlotCode("existing"),
        parent_id=None,
        placement=_placement(uuid4()),
        drawing=None,
        installed_asset_id=None,
        status=MountStatus.ACTIVE,
    )
    with pytest.raises(MountAlreadyExistsError) as info:
        register_mount.decide(
            state=existing,
            command=RegisterMount(
                slot_code="new",
                parent_id=None,
                placement=_placement(uuid4()),
                drawing=None,
            ),
            context=RegisterMountContext(existing_mount_id=None),
            now=_NOW,
            new_id=uuid4(),
        )
    assert info.value.mount_id == existing.id


@pytest.mark.unit
def test_decide_rejects_colliding_slot_code() -> None:
    """Projection precondition: slot_code already in use."""
    pre_existing_mount = uuid4()
    with pytest.raises(MountAlreadyExistsError) as info:
        register_mount.decide(
            state=None,
            command=RegisterMount(
                slot_code="02-BM-A-K-01",
                parent_id=None,
                placement=_placement(uuid4()),
                drawing=None,
            ),
            context=RegisterMountContext(existing_mount_id=pre_existing_mount),
            now=_NOW,
            new_id=uuid4(),
        )
    assert info.value.mount_id == pre_existing_mount


@pytest.mark.unit
def test_decide_rejects_whitespace_only_slot_code() -> None:
    with pytest.raises(InvalidSlotCodeError) as info:
        register_mount.decide(
            state=None,
            command=RegisterMount(
                slot_code="   ",
                parent_id=None,
                placement=_placement(uuid4()),
                drawing=None,
            ),
            context=RegisterMountContext(existing_mount_id=None),
            now=_NOW,
            new_id=uuid4(),
        )
    assert info.value.value == "   "
