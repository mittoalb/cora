"""Unit tests for the `restore_from_maintenance` slice's pure decider.

Single-source-state guard: `Maintenance -> Active`. Inverse of
`enter_maintenance`. Strict not-idempotent semantics.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotRestoreFromMaintenanceError,
    AssetLevel,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
    AssetRestoredFromMaintenance,
)
from cora.equipment.features import restore_from_maintenance
from cora.equipment.features.restore_from_maintenance import RestoreFromMaintenance

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _asset(*, lifecycle: AssetLifecycle = AssetLifecycle.MAINTENANCE) -> Asset:
    return Asset(
        id=uuid4(),
        name=AssetName("APS-2BM"),
        level=AssetLevel.UNIT,
        parent_id=uuid4(),
        lifecycle=lifecycle,
    )


@pytest.mark.unit
def test_decide_emits_asset_restored_for_maintenance_asset() -> None:
    state = _asset(lifecycle=AssetLifecycle.MAINTENANCE)
    events = restore_from_maintenance.decide(
        state=state,
        command=RestoreFromMaintenance(asset_id=state.id),
        now=_NOW,
    )
    assert events == [AssetRestoredFromMaintenance(asset_id=state.id, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_raises_asset_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        restore_from_maintenance.decide(
            state=None,
            command=RestoreFromMaintenance(asset_id=target_id),
            now=_NOW,
        )
    assert exc_info.value.asset_id == target_id


@pytest.mark.unit
@pytest.mark.parametrize(
    "current",
    [
        AssetLifecycle.COMMISSIONED,
        AssetLifecycle.ACTIVE,
        AssetLifecycle.DECOMMISSIONED,
    ],
)
def test_decide_raises_cannot_restore_for_every_disallowed_source(
    current: AssetLifecycle,
) -> None:
    """Strict semantics: Maintenance is the only valid source. Pinned
    that calling restore on an already-Active asset raises (the
    maintenance window has already ended), and that
    Commissioned / Decommissioned are both rejected."""
    state = _asset(lifecycle=current)
    with pytest.raises(AssetCannotRestoreFromMaintenanceError) as exc_info:
        restore_from_maintenance.decide(
            state=state,
            command=RestoreFromMaintenance(asset_id=state.id),
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert exc_info.value.current_lifecycle is current


@pytest.mark.unit
def test_decide_error_message_lists_maintenance_as_required_source() -> None:
    state = _asset(lifecycle=AssetLifecycle.ACTIVE)
    with pytest.raises(AssetCannotRestoreFromMaintenanceError) as exc_info:
        restore_from_maintenance.decide(
            state=state,
            command=RestoreFromMaintenance(asset_id=state.id),
            now=_NOW,
        )
    msg = str(exc_info.value)
    assert "Active" in msg
    assert "Maintenance" in msg


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _asset(lifecycle=AssetLifecycle.MAINTENANCE)
    command = RestoreFromMaintenance(asset_id=state.id)
    first = restore_from_maintenance.decide(state=state, command=command, now=_NOW)
    second = restore_from_maintenance.decide(state=state, command=command, now=_NOW)
    assert first == second
