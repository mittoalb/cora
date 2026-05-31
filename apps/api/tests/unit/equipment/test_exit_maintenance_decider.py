"""Unit tests for the `exit_maintenance` slice's pure decider.

Single-source-state guard: `Maintenance -> Active`. Inverse of
`enter_maintenance`. Strict not-idempotent semantics.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotExitMaintenanceError,
    AssetLevel,
    AssetLifecycle,
    AssetMaintenanceExited,
    AssetName,
    AssetNotFoundError,
)
from cora.equipment.features import exit_maintenance
from cora.equipment.features.exit_maintenance import ExitMaintenance

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
def test_decide_emits_asset_maintenance_exited_for_maintenance_asset() -> None:
    state = _asset(lifecycle=AssetLifecycle.MAINTENANCE)
    events = exit_maintenance.decide(
        state=state,
        command=ExitMaintenance(asset_id=state.id),
        now=_NOW,
    )
    assert events == [AssetMaintenanceExited(asset_id=state.id, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_raises_asset_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        exit_maintenance.decide(
            state=None,
            command=ExitMaintenance(asset_id=target_id),
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
def test_decide_raises_cannot_exit_for_every_disallowed_source(
    current: AssetLifecycle,
) -> None:
    """Strict semantics: Maintenance is the only valid source. Pinned
    that calling exit on an already-Active asset raises (the
    maintenance window has already ended), and that
    Commissioned / Decommissioned are both rejected."""
    state = _asset(lifecycle=current)
    with pytest.raises(AssetCannotExitMaintenanceError) as exc_info:
        exit_maintenance.decide(
            state=state,
            command=ExitMaintenance(asset_id=state.id),
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert exc_info.value.current_lifecycle is current


@pytest.mark.unit
def test_decide_error_message_lists_maintenance_as_required_source() -> None:
    state = _asset(lifecycle=AssetLifecycle.ACTIVE)
    with pytest.raises(AssetCannotExitMaintenanceError) as exc_info:
        exit_maintenance.decide(
            state=state,
            command=ExitMaintenance(asset_id=state.id),
            now=_NOW,
        )
    msg = str(exc_info.value)
    assert "Active" in msg
    assert "Maintenance" in msg


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _asset(lifecycle=AssetLifecycle.MAINTENANCE)
    command = ExitMaintenance(asset_id=state.id)
    first = exit_maintenance.decide(state=state, command=command, now=_NOW)
    second = exit_maintenance.decide(state=state, command=command, now=_NOW)
    assert first == second
