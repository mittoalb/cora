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
from cora.equipment.aggregates.asset.events import AssetRegistered
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
