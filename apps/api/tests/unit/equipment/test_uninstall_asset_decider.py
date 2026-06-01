"""Unit tests for the `uninstall_asset` slice's pure decider."""

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
    MountAssetUninstalled,
    MountCannotUpdateError,
    MountIsEmptyError,
    MountNotFoundError,
    MountStatus,
)
from cora.equipment.aggregates.mount.state import SlotCode
from cora.equipment.features import uninstall_asset
from cora.equipment.features.uninstall_asset import UninstallAsset

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
def test_decide_emits_uninstalled_with_state_installed_asset_id() -> None:
    occupant = uuid4()
    mount = _mount(installed_asset_id=occupant)
    events = uninstall_asset.decide(
        state=mount,
        command=UninstallAsset(mount_id=mount.id, reason="cleaning"),
        now=_NOW,
    )
    assert events == [
        MountAssetUninstalled(
            mount_id=mount.id,
            asset_id=occupant,
            reason="cleaning",
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_raises_mount_not_found_when_state_is_none() -> None:
    mount_id = uuid4()
    with pytest.raises(MountNotFoundError) as info:
        uninstall_asset.decide(
            state=None,
            command=UninstallAsset(mount_id=mount_id, reason="x"),
            now=_NOW,
        )
    assert info.value.mount_id == mount_id


@pytest.mark.unit
def test_decide_raises_cannot_update_when_mount_decommissioned() -> None:
    mount = _mount(status=MountStatus.DECOMMISSIONED, installed_asset_id=uuid4())
    with pytest.raises(MountCannotUpdateError) as info:
        uninstall_asset.decide(
            state=mount,
            command=UninstallAsset(mount_id=mount.id, reason="x"),
            now=_NOW,
        )
    assert "Decommissioned" in info.value.reason


@pytest.mark.unit
def test_decide_raises_is_empty_when_slot_is_vacant() -> None:
    mount = _mount(installed_asset_id=None)
    with pytest.raises(MountIsEmptyError) as info:
        uninstall_asset.decide(
            state=mount,
            command=UninstallAsset(mount_id=mount.id, reason="x"),
            now=_NOW,
        )
    assert info.value.mount_id == mount.id
