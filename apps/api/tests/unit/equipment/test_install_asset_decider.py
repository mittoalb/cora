"""Unit tests for the `install_asset` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates._placement import (
    Placement,
    ReferenceSurface,
    UnitSystem,
)
from cora.equipment.aggregates.mount import (
    AssetNotFoundForMountError,
    Mount,
    MountAlreadyOccupiedError,
    MountAssetInstalled,
    MountCannotUpdateError,
    MountNotFoundError,
    MountStatus,
)
from cora.equipment.aggregates.mount.state import SlotCode
from cora.equipment.features import install_asset
from cora.equipment.features.install_asset import InstallAsset, InstallAssetContext

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)


def _placement(parent_frame: object) -> Placement:
    return Placement(
        x=0.0,
        y=0.0,
        z=0.0,
        rx=0.0,
        ry=0.0,
        rz=0.0,
        parent_frame=parent_frame,  # type: ignore[arg-type]
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
def test_decide_emits_asset_installed_for_vacant_active_mount_with_existing_asset() -> None:
    mount = _mount()
    asset_id = uuid4()
    events = install_asset.decide(
        state=mount,
        command=InstallAsset(mount_id=mount.id, asset_id=asset_id),
        context=InstallAssetContext(asset_exists=True),
        now=_NOW,
    )
    assert events == [
        MountAssetInstalled(
            mount_id=mount.id,
            asset_id=asset_id,
            previously_installed_asset_id=None,
            occurred_at=_NOW,
        )
    ]


@pytest.mark.unit
def test_decide_raises_mount_not_found_when_state_is_none() -> None:
    mount_id = uuid4()
    with pytest.raises(MountNotFoundError) as info:
        install_asset.decide(
            state=None,
            command=InstallAsset(mount_id=mount_id, asset_id=uuid4()),
            context=InstallAssetContext(asset_exists=True),
            now=_NOW,
        )
    assert info.value.mount_id == mount_id


@pytest.mark.unit
def test_decide_raises_cannot_update_when_mount_decommissioned() -> None:
    mount = _mount(status=MountStatus.DECOMMISSIONED)
    with pytest.raises(MountCannotUpdateError) as info:
        install_asset.decide(
            state=mount,
            command=InstallAsset(mount_id=mount.id, asset_id=uuid4()),
            context=InstallAssetContext(asset_exists=True),
            now=_NOW,
        )
    assert "Decommissioned" in info.value.reason


@pytest.mark.unit
def test_decide_raises_already_occupied_when_slot_holds_another_asset() -> None:
    occupant = uuid4()
    attempted = uuid4()
    mount = _mount(installed_asset_id=occupant)
    with pytest.raises(MountAlreadyOccupiedError) as info:
        install_asset.decide(
            state=mount,
            command=InstallAsset(mount_id=mount.id, asset_id=attempted),
            context=InstallAssetContext(asset_exists=True),
            now=_NOW,
        )
    assert info.value.mount_id == mount.id
    assert info.value.installed_asset_id == occupant
    assert info.value.attempted_asset_id == attempted


@pytest.mark.unit
def test_decide_raises_asset_not_found_when_context_asset_missing() -> None:
    mount = _mount()
    asset_id = uuid4()
    with pytest.raises(AssetNotFoundForMountError) as info:
        install_asset.decide(
            state=mount,
            command=InstallAsset(mount_id=mount.id, asset_id=asset_id),
            context=InstallAssetContext(asset_exists=False),
            now=_NOW,
        )
    assert info.value.asset_id == asset_id


@pytest.mark.unit
def test_decide_raises_asset_not_found_before_already_occupied() -> None:
    mount = _mount(installed_asset_id=uuid4())
    bogus_asset_id = uuid4()
    with pytest.raises(AssetNotFoundForMountError) as info:
        install_asset.decide(
            state=mount,
            command=InstallAsset(mount_id=mount.id, asset_id=bogus_asset_id),
            context=InstallAssetContext(asset_exists=False),
            now=_NOW,
        )
    assert info.value.asset_id == bogus_asset_id
