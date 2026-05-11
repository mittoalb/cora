"""Unit tests for the `remove_asset_capability` slice's pure decider.

Mirror of `test_add_asset_capability_decider.py`. Two disqualifying
conditions surface as `AssetCannotRemoveCapabilityError`:

  - asset is `Decommissioned`
  - capability NOT in `state.capabilities` (strict-not-idempotent)
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotRemoveCapabilityError,
    AssetCapabilityRemoved,
    AssetLevel,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
)
from cora.equipment.features import remove_asset_capability
from cora.equipment.features.remove_asset_capability import RemoveAssetCapability

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _asset(
    *,
    lifecycle: AssetLifecycle = AssetLifecycle.ACTIVE,
    capabilities: frozenset[uuid4] = frozenset(),  # type: ignore[assignment]
) -> Asset:
    return Asset(
        id=uuid4(),
        name=AssetName("APS-2BM"),
        level=AssetLevel.UNIT,
        parent_id=uuid4(),
        lifecycle=lifecycle,
        capabilities=capabilities,  # type: ignore[arg-type]
    )


@pytest.mark.unit
def test_decide_emits_asset_capability_removed_for_present_capability() -> None:
    cap1 = uuid4()
    state = _asset(capabilities=frozenset({cap1}))
    events = remove_asset_capability.decide(
        state=state,
        command=RemoveAssetCapability(asset_id=state.id, capability_id=cap1),
        now=_NOW,
    )
    assert events == [
        AssetCapabilityRemoved(asset_id=state.id, capability_id=cap1, occurred_at=_NOW)
    ]


@pytest.mark.unit
def test_decide_raises_asset_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        remove_asset_capability.decide(
            state=None,
            command=RemoveAssetCapability(asset_id=target_id, capability_id=uuid4()),
            now=_NOW,
        )
    assert exc_info.value.asset_id == target_id


@pytest.mark.unit
def test_decide_raises_cannot_remove_when_asset_is_decommissioned() -> None:
    cap1 = uuid4()
    # Even though the capability is present, Decommissioned takes precedence
    # over the not-present check (decommission guard ordered first in the decider).
    state = _asset(lifecycle=AssetLifecycle.DECOMMISSIONED, capabilities=frozenset({cap1}))
    with pytest.raises(AssetCannotRemoveCapabilityError) as exc_info:
        remove_asset_capability.decide(
            state=state,
            command=RemoveAssetCapability(asset_id=state.id, capability_id=cap1),
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert exc_info.value.capability_id == cap1
    assert "Decommissioned" in exc_info.value.reason


@pytest.mark.unit
def test_decide_raises_cannot_remove_when_capability_not_present() -> None:
    """Strict-not-idempotent: removing a capability not in the set
    raises rather than no-op."""
    cap_present = uuid4()
    cap_absent = uuid4()
    state = _asset(capabilities=frozenset({cap_present}))
    with pytest.raises(AssetCannotRemoveCapabilityError) as exc_info:
        remove_asset_capability.decide(
            state=state,
            command=RemoveAssetCapability(asset_id=state.id, capability_id=cap_absent),
            now=_NOW,
        )
    assert exc_info.value.capability_id == cap_absent
    assert "not in" in exc_info.value.reason


@pytest.mark.unit
@pytest.mark.parametrize(
    "lifecycle",
    [
        AssetLifecycle.COMMISSIONED,
        AssetLifecycle.ACTIVE,
        AssetLifecycle.MAINTENANCE,
    ],
)
def test_decide_succeeds_for_every_non_decommissioned_lifecycle(
    lifecycle: AssetLifecycle,
) -> None:
    cap1 = uuid4()
    state = _asset(lifecycle=lifecycle, capabilities=frozenset({cap1}))
    events = remove_asset_capability.decide(
        state=state,
        command=RemoveAssetCapability(asset_id=state.id, capability_id=cap1),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].capability_id == cap1


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    cap1 = uuid4()
    state = _asset(capabilities=frozenset({cap1}))
    command = RemoveAssetCapability(asset_id=state.id, capability_id=cap1)
    first = remove_asset_capability.decide(state=state, command=command, now=_NOW)
    second = remove_asset_capability.decide(state=state, command=command, now=_NOW)
    assert first == second
