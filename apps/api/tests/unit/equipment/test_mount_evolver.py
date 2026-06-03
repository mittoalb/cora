"""Unit tests for the Mount aggregate's evolver: genesis + transitions."""

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
    Mount,
    MountAssetInstalled,
    MountAssetUninstalled,
    MountDecommissioned,
    MountPlacementUpdated,
    MountRegistered,
    MountStatus,
    evolve,
    fold,
)
from cora.equipment.aggregates.mount.state import SlotCode

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


def _drawing() -> Drawing:
    return Drawing(system=DrawingSystem.ICMS, number="P4105090404-210000-00", revision="A")


@pytest.mark.unit
def test_evolve_genesis_sets_active_status_for_root_mount() -> None:
    mount_id = uuid4()
    frame_id = uuid4()
    event = MountRegistered(
        mount_id=mount_id,
        slot_code="02-BM-A-K-01",
        parent_mount_id=None,
        placement=_placement(frame_id),
        drawing=None,
        occurred_at=_NOW,
    )
    state = evolve(None, event)
    assert state == Mount(
        id=mount_id,
        slot_code=SlotCode("02-BM-A-K-01"),
        parent_mount_id=None,
        placement=_placement(frame_id),
        drawing=None,
        installed_asset_id=None,
        status=MountStatus.ACTIVE,
    )


@pytest.mark.unit
def test_evolve_genesis_sets_active_status_with_parent_and_drawing() -> None:
    mount_id = uuid4()
    parent_mount = uuid4()
    frame_id = uuid4()
    drawing = _drawing()
    event = MountRegistered(
        mount_id=mount_id,
        slot_code="02-BM-A-K-01-CHILD",
        parent_mount_id=parent_mount,
        placement=_placement(frame_id),
        drawing=drawing,
        occurred_at=_NOW,
    )
    state = evolve(None, event)
    assert state.parent_mount_id == parent_mount
    assert state.drawing == drawing
    assert state.installed_asset_id is None
    assert state.status is MountStatus.ACTIVE


@pytest.mark.unit
def test_evolve_placement_updated_changes_only_placement() -> None:
    mount_id = uuid4()
    frame_id = uuid4()
    prior = Mount(
        id=mount_id,
        slot_code=SlotCode("02-BM-A-K-01"),
        parent_mount_id=None,
        placement=_placement(frame_id),
        drawing=None,
        installed_asset_id=None,
        status=MountStatus.ACTIVE,
    )
    new_placement = _placement(frame_id, z=259999.0)
    event = MountPlacementUpdated(
        mount_id=mount_id,
        new_placement=new_placement,
        survey=None,
        occurred_at=_NOW,
    )
    state = evolve(prior, event)
    assert state.placement == new_placement
    assert state.slot_code == prior.slot_code
    assert state.status is MountStatus.ACTIVE
    assert state.installed_asset_id is None


@pytest.mark.unit
def test_evolve_asset_installed_sets_installed_asset_id() -> None:
    mount_id = uuid4()
    asset_id = uuid4()
    frame_id = uuid4()
    prior = Mount(
        id=mount_id,
        slot_code=SlotCode("02-BM-A-K-01"),
        parent_mount_id=None,
        placement=_placement(frame_id),
        drawing=None,
        installed_asset_id=None,
        status=MountStatus.ACTIVE,
    )
    event = MountAssetInstalled(
        mount_id=mount_id,
        asset_id=asset_id,
        previously_installed_asset_id=None,
        occurred_at=_NOW,
    )
    state = evolve(prior, event)
    assert state.installed_asset_id == asset_id
    assert state.status is MountStatus.ACTIVE


@pytest.mark.unit
def test_evolve_asset_installed_replaces_prior_specimen_in_swap_within_cycle() -> None:
    """Swap shape: install_asset on a slot that just held another Asset
    sets installed_asset_id to the new asset_id (the prior asset is
    folded out, the audit trail keeps both in the payload)."""
    mount_id = uuid4()
    prior_asset = uuid4()
    new_asset = uuid4()
    frame_id = uuid4()
    prior = Mount(
        id=mount_id,
        slot_code=SlotCode("02-BM-A-K-01"),
        parent_mount_id=None,
        placement=_placement(frame_id),
        drawing=None,
        installed_asset_id=prior_asset,
        status=MountStatus.ACTIVE,
    )
    event = MountAssetInstalled(
        mount_id=mount_id,
        asset_id=new_asset,
        previously_installed_asset_id=prior_asset,
        occurred_at=_NOW,
    )
    state = evolve(prior, event)
    assert state.installed_asset_id == new_asset


@pytest.mark.unit
def test_evolve_asset_uninstalled_clears_installed_asset_id() -> None:
    mount_id = uuid4()
    asset_id = uuid4()
    frame_id = uuid4()
    prior = Mount(
        id=mount_id,
        slot_code=SlotCode("02-BM-A-K-01"),
        parent_mount_id=None,
        placement=_placement(frame_id),
        drawing=None,
        installed_asset_id=asset_id,
        status=MountStatus.ACTIVE,
    )
    event = MountAssetUninstalled(
        mount_id=mount_id,
        asset_id=asset_id,
        reason="removed for cleaning",
        occurred_at=_NOW,
    )
    state = evolve(prior, event)
    assert state.installed_asset_id is None
    assert state.status is MountStatus.ACTIVE


@pytest.mark.unit
def test_evolve_mount_decommissioned_sets_terminal_status() -> None:
    mount_id = uuid4()
    frame_id = uuid4()
    drawing = _drawing()
    prior = Mount(
        id=mount_id,
        slot_code=SlotCode("02-BM-A-K-01"),
        parent_mount_id=None,
        placement=_placement(frame_id),
        drawing=drawing,
        installed_asset_id=None,
        status=MountStatus.ACTIVE,
    )
    event = MountDecommissioned(
        mount_id=mount_id,
        reason="slot removed during 2027 reconfiguration",
        occurred_at=_NOW,
    )
    state = evolve(prior, event)
    assert state.status is MountStatus.DECOMMISSIONED
    # all other fields carry through
    assert state.placement == prior.placement
    assert state.drawing == drawing
    assert state.slot_code == prior.slot_code


@pytest.mark.unit
def test_evolve_transition_event_on_empty_state_raises() -> None:
    """Non-genesis events on empty state are stream corruption; raise loud."""
    mount_id = uuid4()
    event = MountDecommissioned(mount_id=mount_id, reason="x", occurred_at=_NOW)
    with pytest.raises(ValueError, match="MountDecommissioned"):
        evolve(None, event)


@pytest.mark.unit
def test_fold_replays_register_install_uninstall_decommission() -> None:
    mount_id = uuid4()
    asset_id = uuid4()
    frame_id = uuid4()
    events = [
        MountRegistered(
            mount_id=mount_id,
            slot_code="02-BM-A-K-01",
            parent_mount_id=None,
            placement=_placement(frame_id),
            drawing=None,
            occurred_at=_NOW,
        ),
        MountAssetInstalled(
            mount_id=mount_id,
            asset_id=asset_id,
            previously_installed_asset_id=None,
            occurred_at=_NOW,
        ),
        MountAssetUninstalled(
            mount_id=mount_id,
            asset_id=asset_id,
            reason="cleaning",
            occurred_at=_NOW,
        ),
        MountDecommissioned(
            mount_id=mount_id,
            reason="slot removed",
            occurred_at=_NOW,
        ),
    ]
    state = fold(events)
    assert state is not None
    assert state.id == mount_id
    assert state.installed_asset_id is None
    assert state.status is MountStatus.DECOMMISSIONED


@pytest.mark.unit
def test_fold_returns_none_for_empty_history() -> None:
    assert fold([]) is None
