"""Unit tests for the `update_mount_placement` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates._placement import (
    Placement,
    ReferenceSurface,
    UnitSystem,
)
from cora.equipment.aggregates.mount import (
    Mount,
    MountCannotUpdateError,
    MountNotFoundError,
    MountPlacementUpdated,
    MountStatus,
)
from cora.equipment.aggregates.mount.state import SlotCode
from cora.equipment.features import update_mount_placement
from cora.equipment.features.update_mount_placement import UpdateMountPlacement

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)


def _placement(parent_frame_id: object, *, z: float = 259313.0) -> Placement:
    return Placement(
        x=0.0,
        y=0.0,
        z=z,
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


def _mount(*, frame_id: object, status: MountStatus = MountStatus.ACTIVE) -> Mount:
    return Mount(
        id=uuid4(),
        slot_code=SlotCode("02-BM-A-K-01"),
        parent_id=None,
        placement=_placement(frame_id),
        drawing=None,
        installed_asset_id=None,
        status=status,
    )


@pytest.mark.unit
def test_decide_emits_placement_updated_for_genuine_change() -> None:
    frame_id = uuid4()
    mount = _mount(frame_id=frame_id)
    new = _placement(frame_id, z=259999.0)
    events = update_mount_placement.decide(
        state=mount,
        command=UpdateMountPlacement(mount_id=mount.id, new_placement=new, survey=None),
        now=_NOW,
    )
    assert events == [
        MountPlacementUpdated(
            mount_id=mount.id,
            new_placement=new,
            survey=None,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_returns_no_op_when_placement_unchanged() -> None:
    frame_id = uuid4()
    mount = _mount(frame_id=frame_id)
    same = _placement(frame_id)
    events = update_mount_placement.decide(
        state=mount,
        command=UpdateMountPlacement(mount_id=mount.id, new_placement=same, survey=None),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_decide_raises_mount_not_found_when_state_is_none() -> None:
    mount_id = uuid4()
    with pytest.raises(MountNotFoundError) as info:
        update_mount_placement.decide(
            state=None,
            command=UpdateMountPlacement(
                mount_id=mount_id,
                new_placement=_placement(uuid4()),
                survey=None,
            ),
            now=_NOW,
        )
    assert info.value.mount_id == mount_id


@pytest.mark.unit
def test_decide_raises_mount_cannot_update_when_decommissioned() -> None:
    frame_id = uuid4()
    mount = _mount(frame_id=frame_id, status=MountStatus.DECOMMISSIONED)
    with pytest.raises(MountCannotUpdateError) as info:
        update_mount_placement.decide(
            state=mount,
            command=UpdateMountPlacement(
                mount_id=mount.id,
                new_placement=_placement(frame_id, z=999.0),
                survey=None,
            ),
            now=_NOW,
        )
    assert info.value.mount_id == mount.id
    assert "Decommissioned" in info.value.reason


@pytest.mark.unit
def test_decide_rejects_reparent_attempt() -> None:
    frame_id = uuid4()
    other_frame = uuid4()
    mount = _mount(frame_id=frame_id)
    with pytest.raises(MountCannotUpdateError) as info:
        update_mount_placement.decide(
            state=mount,
            command=UpdateMountPlacement(
                mount_id=mount.id,
                new_placement=_placement(other_frame, z=999.0),
                survey=None,
            ),
            now=_NOW,
        )
    assert "reparent" in info.value.reason.lower()
