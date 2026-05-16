"""Unit tests for the `add_asset_capability` slice's pure decider.

Two disqualifying conditions both surface as
`AssetCannotAddCapabilityError` with a diagnostic `reason` string
(mirrors the relocate decider's collapsed-conditions pattern):

  - asset is `Decommissioned`
  - capability already in `state.capabilities` (strict-not-idempotent)
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotAddCapabilityError,
    AssetCapabilityAdded,
    AssetLevel,
    AssetLifecycle,
    AssetName,
    AssetNotFoundError,
)
from cora.equipment.features import add_asset_capability
from cora.equipment.features.add_asset_capability import AddAssetCapability

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
def test_decide_emits_asset_capability_added_for_active_asset_without_capability() -> None:
    state = _asset(lifecycle=AssetLifecycle.ACTIVE, capabilities=frozenset())
    new_cap = uuid4()
    events = add_asset_capability.decide(
        state=state,
        command=AddAssetCapability(asset_id=state.id, capability_id=new_cap),
        now=_NOW,
    )
    assert events == [
        AssetCapabilityAdded(asset_id=state.id, capability_id=new_cap, occurred_at=_NOW)
    ]


@pytest.mark.unit
def test_decide_raises_asset_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(AssetNotFoundError) as exc_info:
        add_asset_capability.decide(
            state=None,
            command=AddAssetCapability(asset_id=target_id, capability_id=uuid4()),
            now=_NOW,
        )
    assert exc_info.value.asset_id == target_id


@pytest.mark.unit
def test_decide_raises_cannot_add_when_asset_is_decommissioned() -> None:
    """Retired-from-service assets cannot accept new capabilities."""
    state = _asset(lifecycle=AssetLifecycle.DECOMMISSIONED)
    new_cap = uuid4()
    with pytest.raises(AssetCannotAddCapabilityError) as exc_info:
        add_asset_capability.decide(
            state=state,
            command=AddAssetCapability(asset_id=state.id, capability_id=new_cap),
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert exc_info.value.capability_id == new_cap
    assert "Decommissioned" in exc_info.value.reason


@pytest.mark.unit
def test_decide_raises_cannot_add_when_capability_already_present() -> None:
    """Strict-not-idempotent: re-adding a capability already in the set
    raises rather than no-op. Operator can detect 'wait, this is
    already commissioned' rather than silently no-op."""
    cap1 = uuid4()
    state = _asset(capabilities=frozenset({cap1}))
    with pytest.raises(AssetCannotAddCapabilityError) as exc_info:
        add_asset_capability.decide(
            state=state,
            command=AddAssetCapability(asset_id=state.id, capability_id=cap1),
            now=_NOW,
        )
    assert exc_info.value.asset_id == state.id
    assert exc_info.value.capability_id == cap1
    assert "already" in exc_info.value.reason


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
    """Capability changes are allowed in every lifecycle state EXCEPT
    Decommissioned. Pinned: a future change that narrowed the
    allowed-lifecycle set would silently break commissioning workflows
    (which often happen pre-Active during install/test phases)."""
    state = _asset(lifecycle=lifecycle, capabilities=frozenset())
    new_cap = uuid4()
    events = add_asset_capability.decide(
        state=state,
        command=AddAssetCapability(asset_id=state.id, capability_id=new_cap),
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].capability_id == new_cap


@pytest.mark.unit
def test_decide_does_not_validate_capability_existence() -> None:
    """Eventual-consistency stance: decider does NOT verify the
    referenced Capability id refers to a real Capability stream. Same
    precedent as Trust Conduit zone refs (3b) and
    Method.needs_capabilities (6a)."""
    state = _asset()
    bogus_cap = uuid4()
    events = add_asset_capability.decide(
        state=state,
        command=AddAssetCapability(asset_id=state.id, capability_id=bogus_cap),
        now=_NOW,
    )
    assert events[0].capability_id == bogus_cap


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _asset()
    cap = uuid4()
    command = AddAssetCapability(asset_id=state.id, capability_id=cap)
    first = add_asset_capability.decide(state=state, command=command, now=_NOW)
    second = add_asset_capability.decide(state=state, command=command, now=_NOW)
    assert first == second
