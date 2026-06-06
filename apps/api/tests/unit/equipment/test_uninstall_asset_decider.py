"""Unit tests for the `uninstall_asset` slice's pure decider.

Covers the four state-based / context-based preconditions:
  - `MountNotFoundError` when the stream is empty
  - `MountCannotUpdateError` when the Mount is Decommissioned
  - `MountIsEmptyError` when the slot is vacant
  - `MountHasFixtureBoundAssetError` when the installed Asset still
    carries a Fixture back-reference (operator must
    `detach_asset_from_fixture` first; mirrors
    `MountHasAssetInstalledError` on the inverse axis)
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

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
    MountHasFixtureBoundAssetError,
    MountIsEmptyError,
    MountNotFoundError,
    MountStatus,
)
from cora.equipment.aggregates.mount.state import SlotCode
from cora.equipment.features import uninstall_asset
from cora.equipment.features.uninstall_asset import (
    UninstallAsset,
    UninstallAssetContext,
)

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_EMPTY_CONTEXT = UninstallAssetContext(installed_asset_fixture_id=None)


def _placement(parent_frame_id: UUID) -> Placement:
    return Placement(
        x=0.0,
        y=0.0,
        z=0.0,
        rx=0.0,
        ry=0.0,
        rz=0.0,
        parent_frame_id=parent_frame_id,
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
    installed_asset_id: UUID | None = None,
) -> Mount:
    return Mount(
        id=uuid4(),
        slot_code=SlotCode("02-BM-A-K-01"),
        parent_id=None,
        placement=_placement(uuid4()),
        drawing=None,
        installed_asset_id=installed_asset_id,
        status=status,
    )


@pytest.mark.unit
def test_decide_emits_uninstalled_with_state_installed_asset_id() -> None:
    occupant = uuid4()
    mount = _mount(installed_asset_id=occupant)
    events = uninstall_asset.decide(
        state=mount,
        command=UninstallAsset(mount_id=mount.id, reason="cleaning"),
        context=_EMPTY_CONTEXT,
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
            context=_EMPTY_CONTEXT,
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
            context=_EMPTY_CONTEXT,
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
            context=_EMPTY_CONTEXT,
            now=_NOW,
        )
    assert info.value.mount_id == mount.id


@pytest.mark.unit
def test_decide_raises_has_fixture_bound_asset_when_installed_asset_is_attached() -> None:
    """Cross-aggregate guard: an installed Asset that still carries
    a Fixture back-reference cannot be uninstalled; operator must
    detach_asset_from_fixture first.

    Fires AFTER the vacant-slot check (MountIsEmptyError stays the
    first answer for an empty slot) but BEFORE the event is emitted.
    """
    occupant = uuid4()
    fixture_id = uuid4()
    mount = _mount(installed_asset_id=occupant)
    context = UninstallAssetContext(installed_asset_fixture_id=fixture_id)
    with pytest.raises(MountHasFixtureBoundAssetError) as info:
        uninstall_asset.decide(
            state=mount,
            command=UninstallAsset(mount_id=mount.id, reason="x"),
            context=context,
            now=_NOW,
        )
    assert info.value.mount_id == mount.id
    assert info.value.asset_id == occupant
    assert info.value.fixture_id == fixture_id


@pytest.mark.unit
def test_decide_empty_slot_still_takes_precedence_over_fixture_context() -> None:
    """Defensive: if context somehow carries a fixture_id but the
    slot is vacant (impossible in production but a beginner could
    write this), MountIsEmptyError fires first. Vacant-slot is the
    more actionable error.
    """
    mount = _mount(installed_asset_id=None)
    context = UninstallAssetContext(installed_asset_fixture_id=uuid4())
    with pytest.raises(MountIsEmptyError):
        uninstall_asset.decide(
            state=mount,
            command=UninstallAsset(mount_id=mount.id, reason="x"),
            context=context,
            now=_NOW,
        )
