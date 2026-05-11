"""Unit tests for the Asset aggregate's evolver."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetLevel,
    AssetLifecycle,
    AssetName,
    evolve,
    fold,
)
from cora.equipment.aggregates.asset.events import (
    AssetActivated,
    AssetDecommissioned,
    AssetMaintenanceEntered,
    AssetRegistered,
    AssetRelocated,
    AssetRestoredFromMaintenance,
)
from cora.equipment.features import register_asset
from cora.equipment.features.register_asset import RegisterAsset

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_evolve_asset_registered_sets_lifecycle_to_commissioned() -> None:
    """AssetRegistered is the genesis event; lifecycle defaults to
    Commissioned via the evolver. Pin so a future change (e.g. adding
    `initial_lifecycle` to the event payload) is a deliberate
    additive-state evolution."""
    asset_id = uuid4()
    parent_id = uuid4()
    state = evolve(
        None,
        AssetRegistered(
            asset_id=asset_id,
            name="APS-2BM",
            level="Site",
            parent_id=parent_id,
            occurred_at=_NOW,
        ),
    )
    assert state == Asset(
        id=asset_id,
        name=AssetName("APS-2BM"),
        level=AssetLevel.SITE,
        parent_id=parent_id,
        lifecycle=AssetLifecycle.COMMISSIONED,
    )


@pytest.mark.unit
def test_evolve_asset_registered_handles_enterprise_with_null_parent() -> None:
    """The other genesis case: Enterprise-level root has parent_id=None."""
    asset_id = uuid4()
    state = evolve(
        None,
        AssetRegistered(
            asset_id=asset_id,
            name="ANL",
            level="Enterprise",
            parent_id=None,
            occurred_at=_NOW,
        ),
    )
    assert state == Asset(
        id=asset_id,
        name=AssetName("ANL"),
        level=AssetLevel.ENTERPRISE,
        parent_id=None,
        lifecycle=AssetLifecycle.COMMISSIONED,
    )


@pytest.mark.unit
def test_evolve_reconstructs_level_from_payload_string() -> None:
    """`level` is carried in the payload as a string and reconstructed
    via `AssetLevel(level)`. Pin that the round-trip works for every
    level (otherwise an AssetLevel addition would silently break
    persisted streams)."""
    for level in AssetLevel:
        # Enterprise must have null parent; others non-null.
        parent_id = None if level is AssetLevel.ENTERPRISE else uuid4()
        state = evolve(
            None,
            AssetRegistered(
                asset_id=uuid4(),
                name="Anything",
                level=level.value,
                parent_id=parent_id,
                occurred_at=_NOW,
            ),
        )
        assert state.level is level


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_asset_registered_returns_asset() -> None:
    asset_id = uuid4()
    parent_id = uuid4()
    state = fold(
        [
            AssetRegistered(
                asset_id=asset_id,
                name="Eiger-2X-9M",
                level="Device",
                parent_id=parent_id,
                occurred_at=_NOW,
            )
        ]
    )
    assert state == Asset(
        id=asset_id,
        name=AssetName("Eiger-2X-9M"),
        level=AssetLevel.DEVICE,
        parent_id=parent_id,
        lifecycle=AssetLifecycle.COMMISSIONED,
    )


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    asset_id = uuid4()
    parent_id = uuid4()
    events = [
        AssetRegistered(
            asset_id=asset_id,
            name="APS-2BM",
            level="Site",
            parent_id=parent_id,
            occurred_at=_NOW,
        )
    ]
    assert fold(events) == fold(events)


@pytest.mark.unit
def test_decider_and_evolver_round_trip_for_enterprise() -> None:
    """End-to-end: decider produces events that the evolver folds back
    to the expected state. Enterprise-level (the null-parent case)."""
    new_id = uuid4()
    command = RegisterAsset(name="  ANL  ", level=AssetLevel.ENTERPRISE, parent_id=None)
    events = register_asset.decide(state=None, command=command, now=_NOW, new_id=new_id)
    rebuilt = fold(events)
    assert rebuilt == Asset(
        id=new_id,
        name=AssetName("ANL"),
        level=AssetLevel.ENTERPRISE,
        parent_id=None,
        lifecycle=AssetLifecycle.COMMISSIONED,
    )


@pytest.mark.unit
def test_decider_and_evolver_round_trip_for_device_with_parent() -> None:
    """End-to-end: decider produces events that the evolver folds back
    to the expected state. Device-level (the typical with-parent case)."""
    new_id = uuid4()
    parent_id = uuid4()
    command = RegisterAsset(name="Eiger-2X-9M", level=AssetLevel.DEVICE, parent_id=parent_id)
    events = register_asset.decide(state=None, command=command, now=_NOW, new_id=new_id)
    rebuilt = fold(events)
    assert rebuilt == Asset(
        id=new_id,
        name=AssetName("Eiger-2X-9M"),
        level=AssetLevel.DEVICE,
        parent_id=parent_id,
        lifecycle=AssetLifecycle.COMMISSIONED,
    )


# ---------- AssetActivated (Phase 5c) ----------


@pytest.mark.unit
def test_evolve_asset_activated_flips_lifecycle_to_active() -> None:
    """AssetActivated folded onto a Commissioned asset sets
    lifecycle=ACTIVE. Lifecycle field is NOT in the event payload;
    the evolver derives it from the event TYPE (same precedent as
    SubjectMounted)."""
    asset_id = uuid4()
    parent_id = uuid4()
    commissioned = Asset(
        id=asset_id,
        name=AssetName("APS-2BM"),
        level=AssetLevel.UNIT,
        parent_id=parent_id,
        lifecycle=AssetLifecycle.COMMISSIONED,
    )
    activated = evolve(commissioned, AssetActivated(asset_id=asset_id, occurred_at=_NOW))
    assert activated == Asset(
        id=asset_id,
        name=AssetName("APS-2BM"),
        level=AssetLevel.UNIT,
        parent_id=parent_id,
        lifecycle=AssetLifecycle.ACTIVE,
    )


@pytest.mark.unit
def test_evolve_asset_activated_preserves_id_name_level_parent() -> None:
    """The evolver only updates `lifecycle`; id/name/level/parent_id
    are carried over from prior state. Pinned because Asset has more
    state fields than the simpler aggregates — a refactor that built
    Asset from event fields only would silently drop them."""
    asset_id = uuid4()
    parent_id = uuid4()
    commissioned = Asset(
        id=asset_id,
        name=AssetName("Original"),
        level=AssetLevel.DEVICE,
        parent_id=parent_id,
        lifecycle=AssetLifecycle.COMMISSIONED,
    )
    activated = evolve(commissioned, AssetActivated(asset_id=asset_id, occurred_at=_NOW))
    assert activated.id == asset_id
    assert activated.name == AssetName("Original")
    assert activated.level is AssetLevel.DEVICE
    assert activated.parent_id == parent_id


@pytest.mark.unit
def test_evolve_asset_activated_on_empty_state_raises() -> None:
    """AssetActivated before AssetRegistered = corrupted stream."""
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, AssetActivated(asset_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_fold_register_then_activate_yields_active_asset() -> None:
    asset_id = uuid4()
    parent_id = uuid4()
    state = fold(
        [
            AssetRegistered(
                asset_id=asset_id,
                name="APS-2BM",
                level="Unit",
                parent_id=parent_id,
                occurred_at=_NOW,
            ),
            AssetActivated(asset_id=asset_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.lifecycle is AssetLifecycle.ACTIVE


# ---------- AssetDecommissioned (Phase 5c) ----------


@pytest.mark.unit
def test_evolve_asset_decommissioned_from_commissioned_flips_to_decommissioned() -> None:
    """Multi-source: Commissioned -> Decommissioned (operator changed
    mind, decommissioning before activation)."""
    asset_id = uuid4()
    commissioned = Asset(
        id=asset_id,
        name=AssetName("APS-2BM"),
        level=AssetLevel.UNIT,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.COMMISSIONED,
    )
    decommed = evolve(commissioned, AssetDecommissioned(asset_id=asset_id, occurred_at=_NOW))
    assert decommed.lifecycle is AssetLifecycle.DECOMMISSIONED


@pytest.mark.unit
def test_evolve_asset_decommissioned_from_active_flips_to_decommissioned() -> None:
    """Multi-source: Active -> Decommissioned (typical retirement
    path). Pinned so a future change that only handles one source
    state in the evolver is caught."""
    asset_id = uuid4()
    active = Asset(
        id=asset_id,
        name=AssetName("APS-2BM"),
        level=AssetLevel.UNIT,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.ACTIVE,
    )
    decommed = evolve(active, AssetDecommissioned(asset_id=asset_id, occurred_at=_NOW))
    assert decommed.lifecycle is AssetLifecycle.DECOMMISSIONED


@pytest.mark.unit
def test_evolve_asset_decommissioned_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, AssetDecommissioned(asset_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_fold_register_activate_decommission_yields_decommissioned_asset() -> None:
    """End-to-end fold: register + activate + decommission produces
    a Decommissioned asset (the typical lifecycle path)."""
    asset_id = uuid4()
    parent_id = uuid4()
    state = fold(
        [
            AssetRegistered(
                asset_id=asset_id,
                name="APS-2BM",
                level="Unit",
                parent_id=parent_id,
                occurred_at=_NOW,
            ),
            AssetActivated(asset_id=asset_id, occurred_at=_NOW),
            AssetDecommissioned(asset_id=asset_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.lifecycle is AssetLifecycle.DECOMMISSIONED


@pytest.mark.unit
def test_fold_register_decommission_yields_decommissioned_asset() -> None:
    """End-to-end fold: register + decommission (skipping activate)
    produces a Decommissioned asset. Pinned because the multi-source
    contract has to be honored at the fold level too, not just the
    decider."""
    asset_id = uuid4()
    parent_id = uuid4()
    state = fold(
        [
            AssetRegistered(
                asset_id=asset_id,
                name="APS-2BM",
                level="Unit",
                parent_id=parent_id,
                occurred_at=_NOW,
            ),
            AssetDecommissioned(asset_id=asset_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.lifecycle is AssetLifecycle.DECOMMISSIONED


# ---------- AssetRelocated (Phase 5d) ----------


@pytest.mark.unit
def test_evolve_asset_relocated_mutates_parent_id_to_target() -> None:
    """The evolver reads `to_parent_id` (target) and writes it to
    state.parent_id. `from_parent_id` is audit metadata only — not
    read by the evolver. Pinned to lock the source-of-truth contract."""
    asset_id = uuid4()
    old_parent = uuid4()
    new_parent = uuid4()
    commissioned = Asset(
        id=asset_id,
        name=AssetName("APS-2BM"),
        level=AssetLevel.UNIT,
        parent_id=old_parent,
        lifecycle=AssetLifecycle.COMMISSIONED,
    )
    relocated = evolve(
        commissioned,
        AssetRelocated(
            asset_id=asset_id,
            from_parent_id=old_parent,
            to_parent_id=new_parent,
            reason="moved",
            occurred_at=_NOW,
        ),
    )
    assert relocated.parent_id == new_parent


@pytest.mark.unit
def test_evolve_asset_relocated_preserves_lifecycle() -> None:
    """Hierarchy mutation is NOT a state transition — lifecycle is
    carried over from prior state. Pinned because adding a "lifecycle"
    side-effect to relocate would silently change Asset behavior."""
    asset_id = uuid4()
    active = Asset(
        id=asset_id,
        name=AssetName("APS-2BM"),
        level=AssetLevel.UNIT,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.ACTIVE,
    )
    relocated = evolve(
        active,
        AssetRelocated(
            asset_id=asset_id,
            from_parent_id=active.parent_id or uuid4(),
            to_parent_id=uuid4(),
            reason="moved",
            occurred_at=_NOW,
        ),
    )
    assert relocated.lifecycle is AssetLifecycle.ACTIVE


@pytest.mark.unit
def test_evolve_asset_relocated_preserves_id_name_level() -> None:
    """Only parent_id changes. Pinned: the relocate arm has more
    fields to carry than the simple lifecycle transitions."""
    asset_id = uuid4()
    prior = Asset(
        id=asset_id,
        name=AssetName("Original"),
        level=AssetLevel.DEVICE,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.COMMISSIONED,
    )
    relocated = evolve(
        prior,
        AssetRelocated(
            asset_id=asset_id,
            from_parent_id=prior.parent_id or uuid4(),
            to_parent_id=uuid4(),
            reason="moved",
            occurred_at=_NOW,
        ),
    )
    assert relocated.id == asset_id
    assert relocated.name == AssetName("Original")
    assert relocated.level is AssetLevel.DEVICE


@pytest.mark.unit
def test_evolve_asset_relocated_on_empty_state_raises() -> None:
    """Relocate before Register = corrupted stream."""
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(
            None,
            AssetRelocated(
                asset_id=uuid4(),
                from_parent_id=uuid4(),
                to_parent_id=uuid4(),
                reason="moved",
                occurred_at=_NOW,
            ),
        )


@pytest.mark.unit
def test_fold_register_then_relocate_yields_asset_with_new_parent() -> None:
    asset_id = uuid4()
    old_parent = uuid4()
    new_parent = uuid4()
    state = fold(
        [
            AssetRegistered(
                asset_id=asset_id,
                name="APS-2BM",
                level="Unit",
                parent_id=old_parent,
                occurred_at=_NOW,
            ),
            AssetRelocated(
                asset_id=asset_id,
                from_parent_id=old_parent,
                to_parent_id=new_parent,
                reason="site reorganization",
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.parent_id == new_parent
    assert state.lifecycle is AssetLifecycle.COMMISSIONED


@pytest.mark.unit
def test_fold_register_activate_relocate_preserves_active_lifecycle() -> None:
    """Relocate after activate keeps lifecycle=ACTIVE — the typical
    in-service hierarchy move case."""
    asset_id = uuid4()
    old_parent = uuid4()
    new_parent = uuid4()
    state = fold(
        [
            AssetRegistered(
                asset_id=asset_id,
                name="APS-2BM",
                level="Unit",
                parent_id=old_parent,
                occurred_at=_NOW,
            ),
            AssetActivated(asset_id=asset_id, occurred_at=_NOW),
            AssetRelocated(
                asset_id=asset_id,
                from_parent_id=old_parent,
                to_parent_id=new_parent,
                reason="moved while in service",
                occurred_at=_NOW,
            ),
        ]
    )
    assert state is not None
    assert state.parent_id == new_parent
    assert state.lifecycle is AssetLifecycle.ACTIVE


# ---------- AssetMaintenanceEntered (Phase 5e) ----------


@pytest.mark.unit
def test_evolve_asset_maintenance_entered_flips_lifecycle_to_maintenance() -> None:
    """AssetMaintenanceEntered folded onto an Active asset sets
    lifecycle=MAINTENANCE. Lifecycle field is NOT in the event
    payload; the evolver derives it from the event TYPE (same
    convention as AssetActivated)."""
    asset_id = uuid4()
    parent_id = uuid4()
    active = Asset(
        id=asset_id,
        name=AssetName("APS-2BM"),
        level=AssetLevel.UNIT,
        parent_id=parent_id,
        lifecycle=AssetLifecycle.ACTIVE,
    )
    in_maintenance = evolve(active, AssetMaintenanceEntered(asset_id=asset_id, occurred_at=_NOW))
    assert in_maintenance == Asset(
        id=asset_id,
        name=AssetName("APS-2BM"),
        level=AssetLevel.UNIT,
        parent_id=parent_id,
        lifecycle=AssetLifecycle.MAINTENANCE,
    )


@pytest.mark.unit
def test_evolve_asset_maintenance_entered_preserves_id_name_level_parent() -> None:
    asset_id = uuid4()
    parent_id = uuid4()
    active = Asset(
        id=asset_id,
        name=AssetName("Original"),
        level=AssetLevel.DEVICE,
        parent_id=parent_id,
        lifecycle=AssetLifecycle.ACTIVE,
    )
    in_maintenance = evolve(active, AssetMaintenanceEntered(asset_id=asset_id, occurred_at=_NOW))
    assert in_maintenance.id == asset_id
    assert in_maintenance.name == AssetName("Original")
    assert in_maintenance.level is AssetLevel.DEVICE
    assert in_maintenance.parent_id == parent_id


@pytest.mark.unit
def test_evolve_asset_maintenance_entered_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, AssetMaintenanceEntered(asset_id=uuid4(), occurred_at=_NOW))


# ---------- AssetRestoredFromMaintenance (Phase 5e) ----------


@pytest.mark.unit
def test_evolve_asset_restored_from_maintenance_flips_lifecycle_to_active() -> None:
    asset_id = uuid4()
    parent_id = uuid4()
    in_maintenance = Asset(
        id=asset_id,
        name=AssetName("APS-2BM"),
        level=AssetLevel.UNIT,
        parent_id=parent_id,
        lifecycle=AssetLifecycle.MAINTENANCE,
    )
    restored = evolve(
        in_maintenance,
        AssetRestoredFromMaintenance(asset_id=asset_id, occurred_at=_NOW),
    )
    assert restored.lifecycle is AssetLifecycle.ACTIVE
    assert restored.id == asset_id
    assert restored.name == AssetName("APS-2BM")
    assert restored.parent_id == parent_id


@pytest.mark.unit
def test_evolve_asset_restored_from_maintenance_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, AssetRestoredFromMaintenance(asset_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_fold_register_activate_enter_maintenance_yields_maintenance_asset() -> None:
    asset_id = uuid4()
    parent_id = uuid4()
    state = fold(
        [
            AssetRegistered(
                asset_id=asset_id,
                name="APS-2BM",
                level="Unit",
                parent_id=parent_id,
                occurred_at=_NOW,
            ),
            AssetActivated(asset_id=asset_id, occurred_at=_NOW),
            AssetMaintenanceEntered(asset_id=asset_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.lifecycle is AssetLifecycle.MAINTENANCE


@pytest.mark.unit
def test_fold_register_activate_enter_restore_yields_active_asset() -> None:
    """Full maintenance round-trip: enter then restore returns to Active."""
    asset_id = uuid4()
    parent_id = uuid4()
    state = fold(
        [
            AssetRegistered(
                asset_id=asset_id,
                name="APS-2BM",
                level="Unit",
                parent_id=parent_id,
                occurred_at=_NOW,
            ),
            AssetActivated(asset_id=asset_id, occurred_at=_NOW),
            AssetMaintenanceEntered(asset_id=asset_id, occurred_at=_NOW),
            AssetRestoredFromMaintenance(asset_id=asset_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.lifecycle is AssetLifecycle.ACTIVE


@pytest.mark.unit
def test_fold_register_activate_enter_decommission_yields_decommissioned_asset() -> None:
    """Maintenance is the third allowed source for decommission (5e
    widening). Pinned at fold level so the multi-source contract
    holds end-to-end."""
    asset_id = uuid4()
    parent_id = uuid4()
    state = fold(
        [
            AssetRegistered(
                asset_id=asset_id,
                name="APS-2BM",
                level="Unit",
                parent_id=parent_id,
                occurred_at=_NOW,
            ),
            AssetActivated(asset_id=asset_id, occurred_at=_NOW),
            AssetMaintenanceEntered(asset_id=asset_id, occurred_at=_NOW),
            AssetDecommissioned(asset_id=asset_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.lifecycle is AssetLifecycle.DECOMMISSIONED
