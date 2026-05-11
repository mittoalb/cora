"""Unit tests for the `decommission_asset` slice's pure decider.

First multi-source-state guard in Equipment: `Commissioned | Active
-> Decommissioned`. Tests parametrize across both source states so a
future change that only handles one is caught.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotDecommissionError,
    AssetDecommissioned,
    AssetLevel,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
)
from cora.equipment.features import decommission_asset
from cora.equipment.features.decommission_asset import DecommissionAsset

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _asset(*, lifecycle: AssetLifecycle = AssetLifecycle.COMMISSIONED) -> Asset:
    return Asset(
        id=uuid4(),
        name=AssetName("APS-2BM"),
        level=AssetLevel.UNIT,
        parent_id=uuid4(),
        lifecycle=lifecycle,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "source",
    [
        AssetLifecycle.COMMISSIONED,
        AssetLifecycle.ACTIVE,
        AssetLifecycle.MAINTENANCE,
    ],
)
def test_decide_emits_asset_decommissioned_for_each_allowed_source_lifecycle(
    source: AssetLifecycle,
) -> None:
    """Commissioned, Active, and Maintenance are all valid sources;
    the emitted event is identical regardless of which one preceded
    — no `from_lifecycle` on the event payload. (5e widened the
    source set from the original 5c {Commissioned, Active} to add
    Maintenance.)"""
    state = _asset(lifecycle=source)
    events = decommission_asset.decide(
        state=state,
        command=DecommissionAsset(asset_id=state.id),
        now=_NOW,
    )
    assert events == [AssetDecommissioned(asset_id=state.id, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_raises_asset_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        decommission_asset.decide(
            state=None,
            command=DecommissionAsset(asset_id=target_id),
            now=_NOW,
        )
    assert exc_info.value.asset_id == target_id


@pytest.mark.unit
@pytest.mark.parametrize(
    "current",
    [
        AssetLifecycle.DECOMMISSIONED,
    ],
)
def test_decide_raises_cannot_decommission_for_every_disallowed_source(
    current: AssetLifecycle,
) -> None:
    """Strict semantics, not idempotent: re-decommissioning an
    already-`Decommissioned` asset raises. After 5e widened the
    source set to {Commissioned, Active, Maintenance}, Decommissioned
    is the only state left from which decommission is disallowed
    (the parametrize stays for shape symmetry with allowed-source
    test above; future state additions outside the allowed set go
    here)."""
    state = _asset(lifecycle=current)
    with pytest.raises(AssetCannotDecommissionError) as exc_info:
        decommission_asset.decide(
            state=state,
            command=DecommissionAsset(asset_id=state.id),
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert exc_info.value.current_lifecycle is current


@pytest.mark.unit
def test_decide_error_message_lists_all_three_allowed_source_lifecycles() -> None:
    """Pinned because the route's 409 body surfaces this string and
    the operator needs to see ALL THREE allowed source states (after
    5e widened to include Maintenance) to diagnose 'why can't I
    decommission'."""
    state = _asset(lifecycle=AssetLifecycle.DECOMMISSIONED)
    with pytest.raises(AssetCannotDecommissionError) as exc_info:
        decommission_asset.decide(
            state=state,
            command=DecommissionAsset(asset_id=state.id),
            now=_NOW,
        )
    msg = str(exc_info.value)
    assert "Decommissioned" in msg
    assert "Commissioned" in msg
    assert "Active" in msg
    assert "Maintenance" in msg


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _asset(lifecycle=AssetLifecycle.ACTIVE)
    command = DecommissionAsset(asset_id=state.id)
    first = decommission_asset.decide(state=state, command=command, now=_NOW)
    second = decommission_asset.decide(state=state, command=command, now=_NOW)
    assert first == second
