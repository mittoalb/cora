"""Unit tests for the `decommission_mount` slice's pure decider."""

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
    MountCannotDecommissionError,
    MountDecommissioned,
    MountHasActiveChildrenError,
    MountHasInstalledAssetError,
    MountNotFoundError,
    MountStatus,
)
from cora.equipment.aggregates.mount.state import SlotCode
from cora.equipment.features import decommission_mount
from cora.equipment.features.decommission_mount import (
    DecommissionMount,
    DecommissionMountContext,
)

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)


def _placement(parent_frame_id: object) -> Placement:
    return Placement(
        x=0.0,
        y=0.0,
        z=0.0,
        rx=0.0,
        ry=0.0,
        rz=0.0,
        parent_frame_id=parent_frame_id,  # type: ignore[arg-type]
        reference_surface=ReferenceSurface.SHIELDING_FACE,
        tol_x=0.0,
        tol_y=0.0,
        tol_z=0.0,
        tol_rx=0.0,
        tol_ry=0.0,
        tol_rz=0.0,
        units=UnitSystem.SI_MM_RAD,
    )


def _mount(
    *,
    status: MountStatus = MountStatus.ACTIVE,
    installed_asset_id: object = None,
) -> Mount:
    return Mount(
        id=uuid4(),
        slot_code=SlotCode("02-BM-A-K-01"),
        parent_mount_id=None,
        placement=_placement(uuid4()),
        drawing=None,
        installed_asset_id=installed_asset_id,  # type: ignore[arg-type]
        status=status,
    )


@pytest.mark.unit
def test_decide_emits_decommissioned_for_active_vacant_childless_mount() -> None:
    mount = _mount()
    events = decommission_mount.decide(
        state=mount,
        command=DecommissionMount(mount_id=mount.id, reason="reconfig"),
        context=DecommissionMountContext(active_child_mount_ids=()),
        now=_NOW,
    )
    assert events == [MountDecommissioned(mount_id=mount.id, reason="reconfig", occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_raises_mount_not_found_when_state_is_none() -> None:
    mount_id = uuid4()
    with pytest.raises(MountNotFoundError) as info:
        decommission_mount.decide(
            state=None,
            command=DecommissionMount(mount_id=mount_id, reason="x"),
            context=DecommissionMountContext(active_child_mount_ids=()),
            now=_NOW,
        )
    assert info.value.mount_id == mount_id


@pytest.mark.unit
def test_decide_raises_cannot_decommission_when_already_decommissioned() -> None:
    mount = _mount(status=MountStatus.DECOMMISSIONED)
    with pytest.raises(MountCannotDecommissionError) as info:
        decommission_mount.decide(
            state=mount,
            command=DecommissionMount(mount_id=mount.id, reason="x"),
            context=DecommissionMountContext(active_child_mount_ids=()),
            now=_NOW,
        )
    assert info.value.mount_id == mount.id
    assert "Decommissioned" in info.value.reason


@pytest.mark.unit
def test_decide_raises_has_installed_asset_when_slot_is_occupied() -> None:
    occupant = uuid4()
    mount = _mount(installed_asset_id=occupant)
    with pytest.raises(MountHasInstalledAssetError) as info:
        decommission_mount.decide(
            state=mount,
            command=DecommissionMount(mount_id=mount.id, reason="x"),
            context=DecommissionMountContext(active_child_mount_ids=()),
            now=_NOW,
        )
    assert info.value.mount_id == mount.id
    assert info.value.installed_asset_id == occupant


@pytest.mark.unit
def test_decide_raises_has_active_children_when_children_remain() -> None:
    mount = _mount()
    child_a = uuid4()
    child_b = uuid4()
    with pytest.raises(MountHasActiveChildrenError) as info:
        decommission_mount.decide(
            state=mount,
            command=DecommissionMount(mount_id=mount.id, reason="x"),
            context=DecommissionMountContext(active_child_mount_ids=(child_a, child_b)),
            now=_NOW,
        )
    assert info.value.mount_id == mount.id
    assert info.value.active_child_mount_ids == (child_a, child_b)
