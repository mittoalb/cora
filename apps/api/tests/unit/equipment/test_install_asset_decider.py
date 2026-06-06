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
    AssetAlreadyInstalledElsewhereError,
    AssetNotFoundForMountError,
    AssetNotInstallableError,
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
        parent_id=None,
        placement=_placement(uuid4()),
        drawing=None,
        installed_asset_id=installed_asset_id,  # type: ignore[arg-type]
        status=status,
    )


def _ctx(
    *,
    asset_lifecycle: str | None = "Active",
    currently_installed_at_mount_id: object = None,
) -> InstallAssetContext:
    return InstallAssetContext(
        asset_lifecycle=asset_lifecycle,
        currently_installed_at_mount_id=currently_installed_at_mount_id,  # type: ignore[arg-type]
    )


@pytest.mark.unit
def test_decide_emits_asset_installed_for_vacant_active_mount_with_active_asset() -> None:
    mount = _mount()
    asset_id = uuid4()
    events = install_asset.decide(
        state=mount,
        command=InstallAsset(mount_id=mount.id, asset_id=asset_id),
        context=_ctx(),
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
            context=_ctx(),
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
            context=_ctx(),
            now=_NOW,
        )
    assert "Decommissioned" in info.value.reason


@pytest.mark.unit
def test_decide_returns_no_op_when_same_asset_already_installed_here() -> None:
    """Same-asset idempotency per PUT's RFC 9110 contract: repeating
    install(X) against a slot already holding X returns []. Network
    retries must not surface 409."""
    asset_id = uuid4()
    mount = _mount(installed_asset_id=asset_id)
    events = install_asset.decide(
        state=mount,
        command=InstallAsset(mount_id=mount.id, asset_id=asset_id),
        context=_ctx(),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_decide_returns_no_op_even_when_context_says_asset_missing() -> None:
    """Idempotency check fires BEFORE projection-context checks. If the
    slot already holds the requested Asset, the requested state is
    already true; downstream projection lookups are skipped (relevant
    for projection-lag scenarios where the back-lookup might not yet
    reflect a recent install)."""
    asset_id = uuid4()
    mount = _mount(installed_asset_id=asset_id)
    events = install_asset.decide(
        state=mount,
        command=InstallAsset(mount_id=mount.id, asset_id=asset_id),
        context=_ctx(asset_lifecycle=None),
        now=_NOW,
    )
    assert events == []


@pytest.mark.unit
def test_decide_raises_already_occupied_when_slot_holds_another_asset() -> None:
    occupant = uuid4()
    attempted = uuid4()
    mount = _mount(installed_asset_id=occupant)
    with pytest.raises(MountAlreadyOccupiedError) as info:
        install_asset.decide(
            state=mount,
            command=InstallAsset(mount_id=mount.id, asset_id=attempted),
            context=_ctx(),
            now=_NOW,
        )
    assert info.value.mount_id == mount.id
    assert info.value.installed_asset_id == occupant
    assert info.value.attempted_asset_id == attempted


@pytest.mark.unit
def test_decide_raises_asset_not_found_when_context_lifecycle_is_none() -> None:
    mount = _mount()
    asset_id = uuid4()
    with pytest.raises(AssetNotFoundForMountError) as info:
        install_asset.decide(
            state=mount,
            command=InstallAsset(mount_id=mount.id, asset_id=asset_id),
            context=_ctx(asset_lifecycle=None),
            now=_NOW,
        )
    assert info.value.asset_id == asset_id


@pytest.mark.unit
@pytest.mark.parametrize(
    "lifecycle",
    ["Commissioned", "Maintenance", "Decommissioned"],
)
def test_decide_raises_not_installable_for_non_active_lifecycle(lifecycle: str) -> None:
    """Only Active assets are installable. Pre-service Commissioned,
    pulled-for-repair Maintenance, and retired Decommissioned all
    reject. Mirrors mount_subject's Active-Asset-only precedent."""
    mount = _mount()
    asset_id = uuid4()
    with pytest.raises(AssetNotInstallableError) as info:
        install_asset.decide(
            state=mount,
            command=InstallAsset(mount_id=mount.id, asset_id=asset_id),
            context=_ctx(asset_lifecycle=lifecycle),
            now=_NOW,
        )
    assert info.value.asset_id == asset_id
    assert info.value.current_lifecycle == lifecycle


@pytest.mark.unit
def test_decide_raises_already_installed_elsewhere_for_cross_mount_collision() -> None:
    """Single-source-of-truth invariant: an Asset cannot occupy two
    Mount slots at once. Operator must uninstall from the current
    Mount before installing in another."""
    mount = _mount()
    asset_id = uuid4()
    other_mount_id = uuid4()
    with pytest.raises(AssetAlreadyInstalledElsewhereError) as info:
        install_asset.decide(
            state=mount,
            command=InstallAsset(mount_id=mount.id, asset_id=asset_id),
            context=_ctx(currently_installed_at_mount_id=other_mount_id),
            now=_NOW,
        )
    assert info.value.asset_id == asset_id
    assert info.value.currently_at_mount_id == other_mount_id
    assert info.value.attempted_mount_id == mount.id


@pytest.mark.unit
def test_decide_proceeds_when_back_lookup_points_at_this_same_mount() -> None:
    """Projection-lag edge case: the back-lookup says this Asset is
    in THIS Mount but Mount state.installed_asset_id is still None
    (event applied to one projection, not the other yet). The decider
    treats THIS-Mount as not-installed-elsewhere; the slot-occupancy
    check downstream handles the actual conflict. Today this branch
    is unreachable because both projections drain together, but it
    closes the symmetric case."""
    mount = _mount()
    asset_id = uuid4()
    events = install_asset.decide(
        state=mount,
        command=InstallAsset(mount_id=mount.id, asset_id=asset_id),
        context=_ctx(currently_installed_at_mount_id=mount.id),
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
