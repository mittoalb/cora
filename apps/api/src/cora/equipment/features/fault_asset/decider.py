"""Pure decider for the `FaultAsset` command.

Target-state transition: any condition -> Faulted. Mirror of
`degrade_asset.decide` with target FAULTED. Lifecycle is NOT gated.

Invariants:
  - State must not be None (asset must exist) -> AssetNotFoundError
  - No-op on unchanged: if current condition is already Faulted,
    return [] (matches 5g-a's no-op-on-unchanged precedent).
"""

from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCondition,
    AssetFaulted,
    AssetNotFoundError,
)
from cora.equipment.features.fault_asset.command import FaultAsset


def decide(
    state: Asset | None,
    command: FaultAsset,
    *,
    now: datetime,
) -> list[AssetFaulted]:
    """Decide the events produced by faulting an existing asset."""
    if state is None:
        raise AssetNotFoundError(command.asset_id)
    if state.condition is AssetCondition.FAULTED:
        return []
    return [AssetFaulted(asset_id=state.id, reason=command.reason, occurred_at=now)]
