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
    ],
)
def test_decide_emits_asset_decommissioned_for_each_allowed_source_lifecycle(
    source: AssetLifecycle,
) -> None:
    """Both Commissioned and Active are valid sources; the emitted
    event is identical regardless of which one preceded — no
    `from_lifecycle` on the event payload."""
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
        AssetLifecycle.MAINTENANCE,
        AssetLifecycle.DECOMMISSIONED,
    ],
)
def test_decide_raises_cannot_decommission_for_every_disallowed_source(
    current: AssetLifecycle,
) -> None:
    """Strict semantics, not idempotent: re-decommissioning an
    already-`Decommissioned` asset also raises. Two wrong states
    tested explicitly. The two ALLOWED states are covered separately
    above. (Maintenance is in scope for 5e — when decommission widens
    to a 3-source guard, this test moves it from the disallowed
    parametrize list into the allowed one.)"""
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
def test_decide_error_message_lists_both_allowed_source_lifecycles() -> None:
    """Pinned because the route's 409 body surfaces this string and
    the operator needs to see BOTH allowed source states (not just
    one) to diagnose 'why can't I decommission'."""
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


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _asset(lifecycle=AssetLifecycle.ACTIVE)
    command = DecommissionAsset(asset_id=state.id)
    first = decommission_asset.decide(state=state, command=command, now=_NOW)
    second = decommission_asset.decide(state=state, command=command, now=_NOW)
    assert first == second
